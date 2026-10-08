"""I-01 public GET and plugin-supplied ZIP transport regressions; synthetic API."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlparse
import zipfile
from tools import work_owner_resume as w
from tools.update_automation_dashboard import GitHub
from tests.test_work_owner_resume import fixture

ROOT=Path(__file__).resolve().parents[1]


def public_routes():
    value,facts=fixture()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr(zipfile.ZipInfo('sync-report.json', (2020,1,1,0,0,0)),json.dumps(facts['sync_reports']['20']))
    data=stream.getvalue();digest='sha256:'+hashlib.sha256(data).hexdigest()
    artifact=dict(id=77,name='local-main-sync-20-attempt1',expired=False,digest=digest,workflow_run={'id':20})
    routes={'/branches/main':{'commit':{'sha':facts['main_sha']}},
            '/contents/.github/automation-dashboard.json':{'content':base64.b64encode(json.dumps({'schema_version':1,'repository':w.REPOSITORY,'issues':{'96':facts['policy']}}).encode()).decode()},
            '/issues/96':facts['issue'],'/issues/96/comments':facts['issue_comments'],
            '/pulls/101':facts['pr'],'/issues/101/comments':facts['pr_comments'],'/pulls/101/reviews':[],
            '/actions/workflows':{'workflows':[{'id':i,'path':'.github/workflows/'+name,'state':'active'}
               for i,name in enumerate(('python-tests.yml','pull-local-main.yml','measurement-validation-windows.yml','function-call-analysis-windows.yml'),1)]},
            '/actions/workflows/python-tests.yml/runs':{'workflow_runs':[]},
            '/actions/workflows/pull-local-main.yml/runs':{'workflow_runs':facts['sync_runs']},
            '/actions/runs/20/attempts/1/jobs':{'jobs':facts['jobs']['20']},
            '/actions/runs/20/artifacts':{'artifacts':[artifact]},'/actions/artifacts/77':artifact}
    return value,facts,data,routes


class PublicOpener:
    def __init__(self,routes):self.routes=routes;self.calls=[]
    def open(self,request,timeout):
        if request.method!='GET' or request.has_header('Authorization'):
            raise AssertionError('Public reader must use GET without fabricated credential')
        suffix=urlparse(request.full_url).path.removeprefix('/repos/'+w.REPOSITORY)
        self.calls.append(suffix)
        value=self.routes[suffix]
        if isinstance(value,Exception):raise value
        return io.BytesIO(json.dumps(value).encode('utf-8'))


class PublicReadTransportTests(unittest.TestCase):
    def test_public_get_omits_authorization_but_writes_require_token(self):
        opener=PublicOpener({'/git/ref/heads/main':{'object':{'sha':'a'*40}}})
        with patch('urllib.request.build_opener',return_value=opener):
            api=GitHub()
            self.assertEqual(api.get('/git/ref/heads/main')['object']['sha'],'a'*40)
            for method in ('POST','PATCH'):
                with self.assertRaisesRegex(ValueError,'token'):api.request(api.root+'/issues/96/comments',method,{'body':'synthetic'})
        self.assertEqual(opener.calls,['/git/ref/heads/main'])
    def test_provided_zip_uses_current_api_and_existing_reader(self):
        value,facts,data,routes=public_routes()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'実ZIP.zip';path.write_bytes(data);opener=PublicOpener(routes)
            with patch('urllib.request.build_opener',return_value=opener):
                current=w.read_facts(w.ObservationGitHub(None,path),value)
                self.assertEqual(w.observe(value,current)['status'],'OBSERVED')
            self.assertIn('/actions/artifacts/77',opener.calls)
            self.assertFalse(any(route.endswith('/zip') for route in opener.calls))
            self.assertEqual(path.read_bytes(),data)
    def test_current_metadata_wrong_run_attempt_name_expired_digest_and_api_failure(self):
        cases=[lambda routes:routes['/actions/artifacts/77']['workflow_run'].update(id=21),
               lambda routes:routes['/actions/artifacts/77'].update(name='local-main-sync-20-attempt2'),
               lambda routes:routes['/actions/artifacts/77'].update(expired=True),
               lambda routes:routes['/actions/artifacts/77'].update(id=78),
               lambda routes:routes['/actions/artifacts/77'].update(digest='sha256:'+'f'*64),
               lambda routes:routes.update({'/actions/artifacts/77':OSError('synthetic API unavailable')}),
               lambda routes:routes['/actions/runs/20/artifacts'].update(artifacts=[])]
        for mutate in cases:
            value,facts,data,routes=public_routes()
            # Separate list metadata from single-GET metadata, as the real API does.
            routes['/actions/artifacts/77']=copy.deepcopy(routes['/actions/artifacts/77']);mutate(routes)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'sync.zip';path.write_bytes(data)
                with patch('urllib.request.build_opener',return_value=PublicOpener(routes)):
                    api=w.ObservationGitHub(None,path)
                    try:current=w.read_facts(api,value)
                    except (OSError,ValueError):current={'fetch_error':True}
                    self.assertNotEqual(w.observe(value,current)['status'],'OBSERVED')
    def test_altered_missing_oversize_and_extra_entry_zip_rejected(self):
        for kind in ('altered','missing','oversize','extra_entry'):
            value,facts,data,routes=public_routes()
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'sync.zip'
                if kind=='altered':path.write_bytes(data+b'changed')
                elif kind=='oversize':path.write_bytes(b'X'*2_000_001)
                elif kind=='extra_entry':
                    stream=io.BytesIO()
                    with zipfile.ZipFile(stream,'w') as archive:
                        archive.writestr(zipfile.ZipInfo('sync-report.json', (2020,1,1,0,0,0)),json.dumps(facts['sync_reports']['20']))
                        archive.writestr('execute.py','raise RuntimeError("must never execute")')
                    path.write_bytes(stream.getvalue());digest='sha256:'+hashlib.sha256(stream.getvalue()).hexdigest()
                    routes['/actions/artifacts/77']['digest']=digest
                with patch('urllib.request.build_opener',return_value=PublicOpener(routes)):
                    with self.assertRaises((OSError,ValueError)):w.read_facts(w.ObservationGitHub(None,path),value)
    def test_documented_public_cli_zip_subprocess_utf8_exit_and_reload(self):
        value,facts,data,routes=public_routes()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'handoff.json').write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            (folder/'正式ZIP.zip').write_bytes(data)
            # Child uses actual CLI/urllib Request construction and existing raw ZIP
            # reader. The network is a synthetic current REST service, not live proof.
            shim=folder/'public_cli.py'
            shim.write_text("import sys,runpy,urllib.request\nfrom tests.test_public_read_transport import PublicOpener,public_routes\n_,_,_,routes=public_routes()\nurllib.request.build_opener=lambda *args:PublicOpener(routes)\nrunpy.run_path('tools/work_owner_resume.py',run_name='__main__')\n",encoding='utf-8')
            env={k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN')}
            env['PYTHONPATH']=str(ROOT)
            cmd=[sys.executable,'-B',str(shim),'--handoff',str(folder/'handoff.json'),'--state',str(folder/'state.json'),
                 '--github-read','--sync-artifact-zip',str(folder/'正式ZIP.zip')]
            first=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr.decode('utf-8'))
            out=json.loads((folder/'state.json').read_text(encoding='utf-8'));self.assertEqual(out['status'],'OBSERVED')
            self.assertIn('実動確認済み',first.stdout.decode('utf-8'))
            second=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
            self.assertEqual(second.returncode,0,second.stderr.decode('utf-8'));self.assertIn('NO_OP',second.stdout.decode('utf-8'))
            (folder/'正式ZIP.zip').write_bytes(data+b'changed')
            for _ in range(2):
                failed=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
                self.assertEqual(failed.returncode,1,failed.stderr.decode('utf-8'))
                self.assertEqual(json.loads((folder/'state.json').read_text(encoding='utf-8'))['status'],'STOPPED')
    def test_supplied_zip_cannot_be_fixture_flag_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            command=[sys.executable,'-B','tools/work_owner_resume.py','--handoff','unused.json','--state',str(Path(directory)/'state.json'),
                     '--fixture-facts','unused.json','--sync-artifact-zip','unused.zip']
            result=subprocess.run(command,cwd=ROOT,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertFalse((Path(directory)/'state.json').exists())
