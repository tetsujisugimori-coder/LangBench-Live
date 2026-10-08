import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools import preparation_lifecycle as l
from tools import startup_preparation as p
from tests.test_startup_preparation import input_fixture


def fixture(phase='PRE_IMPLEMENTATION'):
    v=input_fixture(); pr=None if phase=='PRE_IMPLEMENTATION' else 99
    def registration(role, automation):
        return dict(status='SETTINGS_CONFIRMED', id=automation, enabled=True,
                    repository=v['repository'],issue=v['issue'],purpose=v['purpose'],pr=pr,role=role,
                    trigger='pull_request_merged' if role=='owner_resume' else 'pull_request',
                    condition='synthetic saved exact PR conditions',prompt_digest='a'*64,
                    settings_verified=True,event_verified=False,evidence_ref='synthetic://settings')
    r=dict(schema_version=1,input_digest=p.digest(v),phase=phase,pr=pr,
           observed_at='2026-10-08T03:00:00Z',confirmed_by=v['actors']['dispatch'],
           review=registration('review',v['work_automation_id']),owner_resume=registration('owner_resume','b'*32),
           execution={k:None for k in l.EXEC_FIELDS})
    r['review']['event_verified']=phase!='PRE_IMPLEMENTATION'; r['execution']['handoff_ref']='synthetic://handoff'
    return v,r


class LifecycleTests(unittest.TestCase):
    def test_preimplementation_no_future_event(self):
        v,r=fixture(); self.assertEqual(l.assess(v,r)['status'],'PHASE_EVIDENCE_COMPLETE')
    def test_owner_registration_required_premerge(self):
        v,r=fixture('PRE_MERGE'); r['owner_resume'].update(status='NOT_ATTEMPTED',settings_verified=False)
        self.assertEqual(l.assess(v,r)['status'],'WAITING')
    def test_premerge_no_future_execution(self):
        v,r=fixture('PRE_MERGE'); self.assertEqual(l.assess(v,r)['missing'],[])
    def test_postmerge_requires_execution(self):
        v,r=fixture('POST_MERGE'); self.assertEqual(l.assess(v,r)['status'],'WAITING')
    def test_wrong_scope_id_and_missing_settings(self):
        for key,val in [('pr',111),('repository','other/repo'),('role','review'),('id',None),('prompt_digest',None)]:
            v,r=fixture('PRE_MERGE'); r['owner_resume'][key]=val
            with self.subTest(key=key),self.assertRaises(ValueError): l.assess(v,r)
        v,r=fixture(); r['owner_resume']['id']=r['review']['id']
        with self.assertRaises(ValueError): l.assess(v,r)
    def test_closed_not_merged(self):
        v,r=fixture('PRE_MERGE'); r['owner_resume']['trigger']='pull_request_closed'
        self.assertEqual(l.assess(v,r)['status'],'WAITING')
    def test_registered_not_readback(self):
        v,r=fixture('PRE_MERGE'); r['owner_resume'].update(status='REGISTERED',settings_verified=False)
        self.assertEqual(l.assess(v,r)['status'],'WAITING')
    def test_unknown_no_retransmission(self):
        v,r=fixture(); r['owner_resume'].update(status='UNKNOWN',settings_verified=False)
        self.assertIn('no retransmission',l.assess(v,r)['next_action'])
    def test_new_negative_old_positive_noop(self):
        v,r=fixture('PRE_MERGE'); old=l.assess(v,r); neg=copy.deepcopy(r)
        neg['observed_at']='2026-10-08T03:01:00Z'; neg['owner_resume']['enabled']=False
        current=l.assess(v,neg,old); self.assertEqual(current['status'],'WAITING')
        with self.assertRaises(ValueError): l.assess(v,r,current)
        self.assertEqual(l.assess(v,neg,current),current)
    def test_same_time_conflict(self):
        v,r=fixture(); old=l.assess(v,r); r['review']['enabled']=False
        with self.assertRaises(ValueError): l.assess(v,r,old)
    def test_input_rebinding(self):
        v,r=fixture(); old=l.assess(v,r); v['input_version']+=1; r['input_digest']=p.digest(v)
        with self.assertRaises(ValueError): l.assess(v,r,old)
    def test_receipt_before_claim(self):
        v,r=fixture('POST_MERGE'); r['execution'].update(claim_at='2026-10-08T02:00:00Z',receipt_at='2026-10-08T01:00:00Z')
        with self.assertRaises(ValueError): l.assess(v,r)
    def test_unknown_field(self):
        v,r=fixture(); r['invented']=True
        with self.assertRaises(ValueError): l.assess(v,r)
    def test_stop_requires_disabled_readback(self):
        v,r=fixture('FINISHED'); self.assertTrue(any('stop:' in m for m in l.assess(v,r)['missing']))
    def test_cached_pass_not_trusted(self):
        v,r=fixture('POST_MERGE'); old=l.assess(v,r); old.update(status='PHASE_EVIDENCE_COMPLETE',missing=[])
        self.assertEqual(l.assess(v,r,old)['status'],'WAITING')
    def test_cli_legacy_and_sidecar(self):
        v,r=fixture(); root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory); (d/'input.json').write_text(p.canonical(v),encoding='utf-8'); (d/'phase.json').write_text(p.canonical(r),encoding='utf-8')
            cmd=[sys.executable,'-B',str(root/'tools/startup_preparation.py'),'--input',str(d/'input.json'),
                 '--state',str(d/'state.json'),'--output',str(d/'out'),'--config',str(root/'.github/automation-dashboard.json')]
            subprocess.run(cmd,check=True,capture_output=True,cwd=root)
            result=subprocess.run(cmd+['--lifecycle',str(d/'phase.json')],check=True,capture_output=True,cwd=root)
            self.assertIn(b'NOT_CERTIFIED',result.stdout); self.assertTrue((d/'out/owner_resume_registration.md').exists())
            self.assertEqual(p.loads((d/'state.json').read_text(encoding='utf-8'))['schema_version'],1)
