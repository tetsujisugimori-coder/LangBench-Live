"""Actual CLI subprocess with synthetic formal REST records; no live proof."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools import startup_preparation as p, preparation_github as g
from tools.automation_dashboard import validate_policy_config
from tests.test_preparation_evidence import fixture, writer_api, T0, T1, T2, ROOT

SHIM = '''import json,runpy,sys
from pathlib import Path
from tests.test_preparation_evidence import writer_api
from tools import startup_preparation as p
from tools import update_automation_dashboard as u
scenario=json.loads(Path(sys.argv.pop(1)).read_text(encoding='utf-8'))
v,r,f,api=writer_api()
api.config['schema_version']=2
record=scenario['record']
api.comment['body']=p.generate(v,api.config,owner_facts=record)['github_record.md']
if scenario.get('oversize'):api.comment['body']='大'*60000+'\\n'+api.comment['body']
if scenario.get('bad_author'):api.comment['user']={'login':'other','id':1,'type':'User'}
if scenario.get('duplicate'):api.extra=[dict(api.comment,id=101)]
if scenario.get('fail'):
 original=api.get
 count=[0]
 def get(path):
  if path=='/issues/100':
   count[0]+=1
   if count[0]>1:raise OSError('synthetic API failure after author authentication')
  return original(path)
 api.get=get
u.GitHub=lambda *args:api
runpy.run_path('tools/startup_preparation.py',run_name='__main__')
'''

class FormalCLIAuthenticationTests(unittest.TestCase):
    def test_authenticated_negative_api_failure_save_and_two_stale_replays(self):
        for negative in ('disabled','FAILED','UNKNOWN'):
            with self.subTest(negative=negative), tempfile.TemporaryDirectory() as directory:
                d=Path(directory);v,r,f=fixture();config={'schema_version':2,'repository':v['repository'],'issues':{'100':p.policy_entry(v)}}
                for name,item in [('input',v),('owner',r),('config',config)]: (d/(name+'.json')).write_text(p.canonical(item),encoding='utf-8')
                (d/'cli.py').write_text(SHIM,encoding='utf-8')
                cmd=[sys.executable,'-B',str(d/'cli.py'),str(d/'scenario.json'),'--input',str(d/'input.json'),'--owner-facts',str(d/'owner.json'),'--config',str(d/'config.json'),'--state',str(d/'state.json'),'--output',str(d/'out'),'--github-read']
                env={**os.environ,'PYTHONPATH':str(ROOT)};env.pop('GH_TOKEN',None);env.pop('GITHUB_TOKEN',None)
                def run(record,**flags):
                    (d/'scenario.json').write_text(p.canonical(dict(record=record,**flags)),encoding='utf-8')
                    (d/'owner.json').write_text(p.canonical(record),encoding='utf-8')
                    return subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
                first=run(r);self.assertEqual(first.returncode,0,first.stderr.decode())
                positive=copy.deepcopy(r);r['observed_at']=T1;r['review']['observed_at']=T1
                if negative=='disabled':r['review']['settings']['enabled']=False
                else:r['review']['status']=negative
                failed=run(r,fail=True);self.assertEqual(failed.returncode,1,failed.stderr.decode())
                saved=p.loads((d/'state.json').read_text(encoding='utf-8'));self.assertEqual(saved['status'],'STOPPED')
                self.assertEqual(saved['owner_watermarks']['review']['record'],r['review'])
                for _ in range(2):
                    stale=run(positive);self.assertEqual(stale.returncode,0,stale.stderr.decode())
                    saved=p.loads((d/'state.json').read_text(encoding='utf-8'));self.assertEqual(saved['status'],'WAITING')
                    self.assertEqual(saved['owner_watermarks']['review']['record'],r['review'])
    def test_cli_negative_refresh_save_reload_rejects_in_between_positive_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);v,r,f=fixture();config={'schema_version':2,'repository':v['repository'],'issues':{'100':p.policy_entry(v)}}
            for name,item in [('input',v),('owner',r),('config',config)]:
                (d/(name+'.json')).write_text(p.canonical(item),encoding='utf-8')
            (d/'cli.py').write_text(SHIM,encoding='utf-8')
            cmd=[sys.executable,'-B',str(d/'cli.py'),str(d/'scenario.json'),'--input',str(d/'input.json'),
                 '--owner-facts',str(d/'owner.json'),'--config',str(d/'config.json'),
                 '--state',str(d/'state.json'),'--output',str(d/'out'),'--github-read']
            env={**os.environ,'PYTHONPATH':str(ROOT)};env.pop('GH_TOKEN',None);env.pop('GITHUB_TOKEN',None)
            def run(at,enabled=False,revision=1):
                r['observed_at']=at;r['review'].update(observed_at=at,settings_version=revision)
                r['review']['settings']['enabled']=enabled
                (d/'scenario.json').write_text(p.canonical({'record':r}),encoding='utf-8')
                (d/'owner.json').write_text(p.canonical(r),encoding='utf-8')
                result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr.decode('utf-8'))
                return p.loads((d/'state.json').read_text(encoding='utf-8'))
            initial=run(T1);t3='2026-10-08T03:03:00Z';saved=run(t3)
            self.assertEqual(saved['last_progress_at'],initial['last_progress_at'])
            self.assertEqual(saved['owner_watermarks']['review']['record']['observed_at'],t3)
            for _ in range(2):
                saved=run(T2,True,2)
                self.assertEqual(saved['status'],'WAITING')
                self.assertFalse(saved['owner_watermarks']['review']['record']['settings']['enabled'])
                self.assertEqual(saved['owner_watermarks']['review']['record']['observed_at'],t3)
    def test_wrong_author_duplicate_local_owner_mismatch_and_local_draft(self):
        v,r,f,api=writer_api();api.config['schema_version']=2
        self.assertEqual(g.authenticated_cli_record(api,v,r,p.new_state(v))[0]['owner_facts'],r)
        for change in ('author','duplicate','local'):
            v,r,f,api=writer_api();api.config['schema_version']=2;local=copy.deepcopy(r)
            if change=='author':api.comment['user']={'login':'other','id':1,'type':'User'}
            if change=='duplicate':api.extra=[dict(api.comment,id=101)]
            if change=='local':local['publication']['evidence_ref']='synthetic://different'
            with self.assertRaises(ValueError):g.authenticated_cli_record(api,v,local,p.new_state(v))
        # Even owner names equal to public Issue identity cannot authenticate a file.
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            for name,item in [('input',v),('owner',r),('config',{'schema_version':2,'repository':v['repository'],'issues':{}})]: (d/(name+'.json')).write_text(p.canonical(item),encoding='utf-8')
            result=subprocess.run([sys.executable,'-B','tools/startup_preparation.py','--input',str(d/'input.json'),'--owner-facts',str(d/'owner.json'),'--config',str(d/'config.json'),'--state',str(d/'state.json'),'--output',str(d/'out')],cwd=ROOT,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            state=p.loads((d/'state.json').read_text(encoding='utf-8'));self.assertEqual(state['status'],'WAITING');self.assertNotIn('review',state['owner_watermarks'])

class PolicyVersionBarrierTests(unittest.TestCase):
    def test_actual_old_reader_rejects_new_policy_before_token_or_pass(self):
        env={**os.environ,'PYTHONPATH':str(ROOT),'GITHUB_REPOSITORY':p.REPOSITORY};env.pop('GH_TOKEN',None)
        result=subprocess.run([sys.executable,'-B','tests/fixtures/policy_reader_v1_main.py','--config','.github/automation-dashboard.json'],cwd=ROOT,env=env,capture_output=True)
        self.assertEqual(result.returncode,1);self.assertIn('Unexpected repository/config schema',result.stderr.decode());self.assertNotIn('PASS',result.stdout.decode())
    def test_new_reader_legacy_policy_and_old_issue_entries_preserved(self):
        current=json.loads((ROOT/'.github/automation-dashboard.json').read_text(encoding='utf-8'))
        legacy=copy.deepcopy(current);legacy['schema_version']=1;legacy['issues'].pop('100')
        self.assertIs(validate_policy_config(legacy),legacy);self.assertIs(validate_policy_config(current),current)
        for key in ('80','85','88','91','96'):self.assertEqual(legacy['issues'][key],current['issues'][key])
        invalid=copy.deepcopy(current);invalid['schema_version']=1
        with self.assertRaises(ValueError):validate_policy_config(invalid)
        for version in (True,3):
            invalid=copy.deepcopy(current);invalid['schema_version']=version
            with self.assertRaises(ValueError):validate_policy_config(invalid)
