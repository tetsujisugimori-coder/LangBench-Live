"""Bounded same-comment multi-phase roundtrips with synthetic detailed Prompts."""
import copy
import base64
import zlib
import os
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import preparation_evidence as e, preparation_github as g, startup_preparation as p
from tools import work_owner_resume as w
from tests.test_preparation_evidence import fixture, writer_api, T0, ROOT
from tests.test_work_owner_resume import fixture as execution_fixture
from tests.test_preparation_cli_auth import SHIM


def large_fixture(phase,version):
    v,r,f=fixture(phase);v['input_version']=version
    # A synthetic approved detailed Prompt of the user's measured input size.
    # Preserve all existing instructions; pad Japanese detail, never shorten.
    target=10292
    current=len(p.canonical(v).encode('utf-8'))
    filler='日本語の合成承認詳細。' * max(0,(target-current)//len('日本語の合成承認詳細。'.encode('utf-8'))+1)
    v['registration_prompts']['review']['text']+=filler
    v['registration_prompts']['review']['digest']=hashlib.sha256(v['registration_prompts']['review']['text'].encode()).hexdigest()
    r['review']['settings']['prompt']=v['registration_prompts']['review']['text']
    r.update(input_version=version,input_digest=p.digest(v));f.update(input_digest=p.digest(v),main_policy=p.policy_entry(v))
    if phase in ('POST_MERGE','FINISHED'):
        execution,rf=execution_fixture();execution.update(issue=100,pr=89)
        execution['work']['automation_id']=v['owner_resume_id'];execution['event']['pr']=89
        execution['waiting_record']={k:r['waiting_record'][k] for k in ('comment_id','body_sha256')}
        execution['claim']['dedup_key']=w.key(execution)
        execution['receipt'].update(waiting_comment_id=777,waiting_body_sha256=r['waiting_record']['body_sha256'])
        execution['next_action'].update(dedup_key=w.key(execution),authorization_ref=r['waiting_record']['authorization_ref'])
        # Actual handoff-shaped nested fields, clearly synthetic evidence.
        execution['work']['evidence_url']+='/'+'合成handoff実取得相当' * 80
        r['execution']=execution
        if phase=='FINISHED':
            r['stop']=dict(review='synthetic://stop-review',owner_resume='synthetic://stop-resume',observed_at=T0)
            for role in e.ROLES:r[role]['status']='DISABLED_CONFIRMED';r[role]['settings']['enabled']=False
    return v,r,f


class SharedPreparationCapacityTests(unittest.TestCase):
    def test_multiphase_detailed_prompt_handoff_same_comment_writer_and_gate(self):
        v,r,f=large_fixture('PRE_IMPLEMENTATION',1);_,_,_,api=writer_api();api.value=v;api.config['schema_version']=2
        api.config['issues']['100']=p.policy_entry(v);api.comment['body']='Human UTF8 prose 保持\n'
        state=None;max_bytes=0
        for version,phase in enumerate(e.PHASES,1):
            v,r,f=large_fixture(phase,version)
            state=p.rebase(state,v) if state else p.new_state(v)
            request=p.generate(v,api.config,state=state,owner_facts=r)['github_record.md'].strip()
            if e.REQUEST_START in api.comment['body']:
                a=api.comment['body'].index(e.REQUEST_START);b=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
                api.comment['body']=api.comment['body'][:a]+request+api.comment['body'][b:]
            else:api.comment['body']+=request
            with patch.object(g,'current_preparation_facts',return_value=f):
                g.reconcile_preparation(api,100,p.policy_entry(v),T0)
                gate=g.collect_preparation_gate(api,100,p.policy_entry(v))
                self.assertEqual(gate['phase'],phase)
            state=p.loads(p.canonical(g.snapshot(api.comment['body'])['state']))
            self.assertEqual(api.comment['id'],100);self.assertIn('Human UTF8 prose 保持',api.comment['body'])
            self.assertEqual(r['review']['settings']['prompt'],g.authenticated_request(api.comment,100,p.policy_entry(v))['owner_facts']['review']['settings']['prompt'])
            self.assertGreaterEqual(len(p.canonical(v).encode('utf-8')),10292)
            self.assertEqual(len(state['input_history']),version-1)
            max_bytes=max(max_bytes,len(api.comment['body'].encode('utf-8')))
        self.assertGreater(max_bytes,60000)  # Old byte-only limit really rejects this roundtrip.
        self.assertLessEqual(max_bytes,g.PREPARATION_COMMENT_BYTE_LIMIT)
    def test_character_and_byte_boundaries_no_truncation(self):
        self.assertEqual(g.validate_comment_capacity('日'*60000),'日'*60000)
        self.assertEqual(g.validate_comment_capacity('😀'*30000),'😀'*30000)
        for body in ('a'*60001,'😀'*30001):
            with self.assertRaisesRegex(ValueError,'character limit'):g.validate_comment_capacity(body)
        with patch.object(g,'PREPARATION_COMMENT_BYTE_LIMIT',10):
            with self.assertRaisesRegex(ValueError,'UTF-8 byte limit'):g.validate_comment_capacity('日'*4)
    def test_encoded_save_reload_same_observation_twice_noop_and_exact_body(self):
        v,r,f,api=writer_api();g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        body=api.comment['body'];writes=len(api.writes)
        wire=g.block(body,e.SNAPSHOT_START,p.SNAPSHOT_END)
        self.assertEqual(wire['state']['encoding'],'zlib-base64-v1')
        saved=g.snapshot(body);self.assertEqual(saved['state']['input'],v)
        api.comment=p.loads(p.canonical(api.comment))  # Actual serialized comment readback.
        for _ in range(2):
            self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T0),'NO_OP')
            self.assertEqual(api.comment['body'].encode('utf-8'),body.encode('utf-8'))
            self.assertEqual(len(api.writes),writes)
        # Execute the frozen actual old raw-v2 reader, not a simulated version guard.
        import runpy
        old=runpy.run_path(str(ROOT/'tests/fixtures/preparation_raw_v2_snapshot_reader.py'))
        with self.assertRaises(ValueError):old['snapshot_v2'](body)
    def test_legacy_raw_v2_prompt_without_events_requires_explicit_migration(self):
        v,r,f,api=writer_api();old=copy.deepcopy(v)
        for expected in old['registration_prompts'].values():
            if expected is not None:expected.pop('events')
        state=p.new_state(old);state['shared_persistence']=True
        raw=dict(schema_version=2,kind='startup_preparation_snapshot',comment_id=100,
                 input_version=old['input_version'],input_digest=p.digest(old),state=state,source_digest='a'*64)
        raw_body=e.SNAPSHOT_START+p.canonical(raw)+p.SNAPSHOT_END
        self.assertEqual(g.snapshot(raw_body)['state'],state)
        self.assertFalse(e.ready(r['review'],old,'review'))
        api.comment['body']=p.generate(old,api.config)['github_record.md']+raw_body
        with self.assertRaisesRegex(ValueError,'explicit input version migration'):g.authenticate_comment(api.comment,100,p.policy_entry(v))
        v['input_version']=2;r.update(input_version=2,input_digest=p.digest(v))
        migrated=p.rebase(state,v)
        api.comment['body']=p.generate(v,api.config,state=migrated,owner_facts=r)['github_record.md']+raw_body
        g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        saved=g.snapshot(api.comment['body'])['state']
        self.assertEqual(saved['input_history'],[old]);self.assertEqual(saved['input'],v)
    def test_snapshot_codec_raw_compatibility_strict_integrity_and_bounded_decode(self):
        v,r,f=fixture();state=p.new_state(v);encoded=g.encode_snapshot_state(state)
        self.assertEqual(g.decode_snapshot_state(encoded),state)
        self.assertEqual(g.decode_snapshot_state(state),state)
        for field,value in [('encoding','unknown'),('decoded_bytes',True),('decoded_bytes',2_000_001),
                            ('sha256','a'*64),('data','not-base64!'),('extra',True)]:
            bad=copy.deepcopy(encoded);bad[field]=value
            with self.assertRaises(ValueError):g.decode_snapshot_state(bad)
        raw=p.canonical(state).encode()
        for packed in (zlib.compress(raw)+b'extra', zlib.compress(raw)+zlib.compress(raw),
                       zlib.compress(raw)[:-2],zlib.compress(b' '*2_000_001)):
            bad=copy.deepcopy(encoded);bad['data']=base64.b64encode(packed).decode()
            with self.assertRaises(ValueError):g.decode_snapshot_state(bad)
        invalid_state=copy.deepcopy(state);invalid_state['extra']=True
        for raw in (b'\xff',p.canonical(state).encode()+b' ',p.canonical(invalid_state).encode()):
            bad=copy.deepcopy(encoded)
            bad.update(data=base64.b64encode(zlib.compress(raw)).decode(),decoded_bytes=len(raw),
                       sha256=hashlib.sha256(raw).hexdigest())
            with self.assertRaises(ValueError):g.decode_snapshot_state(bad)
    def test_cli_capacity_failure_saves_stopped_and_bound_negative(self):
        v,r,f=fixture();r['review']['settings']['enabled']=False
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            for name,item in [('input',v),('owner',r),('config',{'schema_version':2,'repository':v['repository'],'issues':{'100':p.policy_entry(v)}}),
                              ('scenario',{'record':r,'oversize':True})]:
                (d/(name+'.json')).write_text(p.canonical(item),encoding='utf-8')
            (d/'cli.py').write_text(SHIM,encoding='utf-8')
            env={**os.environ,'PYTHONPATH':str(ROOT)};env.pop('GH_TOKEN',None);env.pop('GITHUB_TOKEN',None)
            result=subprocess.run([sys.executable,'-B',str(d/'cli.py'),str(d/'scenario.json'),
                '--input',str(d/'input.json'),'--owner-facts',str(d/'owner.json'),'--config',str(d/'config.json'),
                '--state',str(d/'state.json'),'--output',str(d/'out'),'--github-read'],cwd=ROOT,env=env,capture_output=True)
            self.assertEqual(result.returncode,1,result.stderr.decode('utf-8'))
            saved=p.loads((d/'state.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['status'],'STOPPED');self.assertIn('capacity',saved['next_action'])
            self.assertFalse(saved['owner_watermarks']['review']['record']['settings']['enabled'])
    def test_capacity_failure_stops_writer_and_collector_before_success_write(self):
        v,r,f,api=writer_api();api.comment['body']='a'*60000+'\n'+api.comment['body']
        with patch.object(g,'current_preparation_facts',return_value=f):
            for reader in (g.reconcile_preparation,g.collect_preparation_gate):
                with self.assertRaisesRegex(ValueError,'capacity'):
                    if reader is g.reconcile_preparation:reader(api,100,p.policy_entry(v),T0)
                    else:reader(api,100,p.policy_entry(v))
        self.assertEqual(api.writes,[]);self.assertTrue(api.comment['body'].startswith('a'*60000))
