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
    def complete_fixture(self, phase):
        v, r = fixture(phase)
        r['review'].update(status='DISABLED_CONFIRMED', enabled=False)
        if phase in ('POST_MERGE', 'FINISHED'):
            r['owner_resume']['event_verified'] = True
            r['execution'].update({k: 'synthetic://' + k for k in l.EXEC_FIELDS
                                   if k not in ('claim_at', 'receipt_at', 'stop_ref')})
            r['execution'].update(claim_at='2026-10-08T02:00:00Z',
                                  receipt_at='2026-10-08T02:01:00Z')
        if phase == 'FINISHED':
            r['owner_resume'].update(status='DISABLED_CONFIRMED', enabled=False)
            r['execution']['stop_ref'] = 'synthetic://stop'
        return v, r

    def test_review_stop_accepted_only_after_implementation(self):
        for phase in l.PHASES:
            with self.subTest(phase=phase):
                v, r = self.complete_fixture(phase)
                before = copy.deepcopy((v, r))
                report = l.assess(v, r)
                self.assertEqual(report['missing'],
                    ['review: registration and saved settings readback']
                    if phase == 'PRE_IMPLEMENTATION' else [])
                self.assertEqual(report['status'], 'WAITING' if phase == 'PRE_IMPLEMENTATION'
                                 else 'PHASE_EVIDENCE_COMPLETE')
                self.assertEqual(report['formal_gate'], 'NOT_CERTIFIED')
                self.assertEqual((v, r), before)
                self.assertEqual(set(report['record']), l.FIELDS)

    def test_active_review_remains_compatible(self):
        for phase in ('PRE_IMPLEMENTATION', 'PRE_MERGE', 'POST_MERGE'):
            with self.subTest(phase=phase):
                v, r = self.complete_fixture(phase)
                r['review'].update(status='SETTINGS_CONFIRMED', enabled=True)
                self.assertEqual(l.assess(v, r)['missing'], [])

    def test_stopped_review_does_not_remove_other_evidence_requirements(self):
        for phase in ('PRE_MERGE', 'POST_MERGE'):
            v, complete = self.complete_fixture(phase)
            with self.subTest(phase=phase, key='review.event_verified'):
                r = copy.deepcopy(complete); r['review']['event_verified'] = False
                self.assertEqual(l.assess(v, r)['missing'], ['review: actual PR event evidence'])
            keys = l.EXEC_FIELDS - {'stop_ref'} if phase == 'POST_MERGE' else {'handoff_ref'}
            for key in keys:
                with self.subTest(phase=phase, key=key):
                    r = copy.deepcopy(complete); r['execution'][key] = None
                    if key == 'claim_at':
                        # validate requires a claim when a receipt is present.
                        with self.assertRaises(ValueError): l.assess(v, r)
                    else:
                        report = l.assess(v, r)
                        self.assertEqual(report['status'], 'WAITING')
                        self.assertIn('execution: ' + key if key != 'handoff_ref'
                                      else 'execution: shared handoff record', report['missing'])
                        self.assertNotIn('review: registration and saved settings readback', report['missing'])
            if phase == 'POST_MERGE':
                r = copy.deepcopy(complete); r['owner_resume']['event_verified'] = False
                self.assertEqual(l.assess(v, r)['missing'], ['owner_resume: actual merge event evidence'])

    def test_stopped_review_validation_still_requires_saved_readback(self):
        for key, invalid in (('settings_verified', False), ('enabled', True),
                             ('id', None), ('evidence_ref', None), ('trigger', None),
                             ('condition', None), ('prompt_digest', None),
                             ('id', 'c' * 32), ('repository', 'other/repo'),
                             ('issue', 999), ('purpose', 'other-purpose'), ('pr', 111),
                             ('role', 'owner_resume')):
            with self.subTest(key=key, invalid=invalid):
                v, r = self.complete_fixture('PRE_MERGE'); r['review'][key] = invalid
                with self.assertRaises(ValueError): l.assess(v, r)
        for key, invalid in (('input_digest', 'f' * 64), ('confirmed_by', 'other-owner')):
            v, r = self.complete_fixture('PRE_MERGE'); r[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError): l.assess(v, r)
        v, r = self.complete_fixture('PRE_MERGE'); r['owner_resume']['id'] = r['review']['id']
        with self.assertRaises(ValueError): l.assess(v, r)

    def test_unconfirmed_or_unresolved_review_stop_remains_waiting(self):
        for phase in ('PRE_MERGE', 'POST_MERGE'):
            for status in ('SETTINGS_CONFIRMED', 'REGISTERED', 'UNKNOWN', 'ATTEMPTING'):
                with self.subTest(phase=phase, status=status):
                    v, r = self.complete_fixture(phase)
                    r['review'].update(status=status, settings_verified=status == 'SETTINGS_CONFIRMED')
                    report = l.assess(v, r)
                    self.assertEqual(report['status'], 'WAITING')
                    self.assertIn('review: registration and saved settings readback', report['missing'])
                    if status in ('UNKNOWN', 'ATTEMPTING'):
                        self.assertIn('no retransmission', report['next_action'])

    def test_owner_early_stop_remains_waiting(self):
        for phase in ('PRE_MERGE', 'POST_MERGE'):
            with self.subTest(phase=phase):
                v, r = self.complete_fixture(phase)
                r['owner_resume'].update(status='DISABLED_CONFIRMED', enabled=False)
                self.assertEqual(l.assess(v, r)['missing'],
                                 ['owner_resume: merge registration and saved settings readback'])

    def test_finished_requires_both_stops_and_stop_evidence(self):
        for role in ('review', 'owner_resume'):
            v, r = self.complete_fixture('FINISHED')
            r[role].update(status='SETTINGS_CONFIRMED', enabled=True)
            with self.subTest(role=role):
                self.assertIn('stop: dedicated registrations disabled readback', l.assess(v, r)['missing'])
        v, r = self.complete_fixture('FINISHED'); r['execution']['stop_ref'] = None
        self.assertEqual(l.assess(v, r)['missing'], ['stop: evidence'])

    def test_stopped_review_does_not_restore_older_positive_event(self):
        v, r = self.complete_fixture('PRE_MERGE'); old = l.assess(v, r)
        negative = copy.deepcopy(r)
        negative['observed_at'] = '2026-10-08T03:01:00Z'
        negative['review']['event_verified'] = False
        current = l.assess(v, negative, old)
        self.assertEqual(current['status'], 'WAITING')
        self.assertEqual(current['history'], [r])
        with self.assertRaises(ValueError): l.assess(v, r, current)
        self.assertEqual(l.assess(v, negative, current), current)

    def test_cli_stopped_review_and_missing_execution(self):
        root = Path(__file__).resolve().parents[1]
        for phase, missing in (('PRE_MERGE', None), ('POST_MERGE', None),
                               ('POST_MERGE', 'sync_ref'), ('FINISHED', None)):
            with self.subTest(phase=phase, missing=missing), tempfile.TemporaryDirectory() as directory:
                v, r = self.complete_fixture(phase)
                if missing: r['execution'][missing] = None
                d = Path(directory)
                (d/'input.json').write_text(p.canonical(v), encoding='utf-8')
                (d/'phase.json').write_text(p.canonical(r), encoding='utf-8')
                result = subprocess.run([sys.executable, '-B', str(root/'tools/startup_preparation.py'),
                    '--input', str(d/'input.json'), '--state', str(d/'state.json'), '--output', str(d/'out'),
                    '--config', str(root/'.github/automation-dashboard.json'), '--lifecycle', str(d/'phase.json')],
                    check=True, capture_output=True, cwd=root)
                report = p.loads((d/'out/lifecycle-assessment.json').read_text(encoding='utf-8'))
                expected = 'WAITING' if missing else 'PHASE_EVIDENCE_COMPLETE'
                self.assertEqual(report['status'], expected)
                self.assertEqual(report['missing'], ['execution: sync_ref'] if missing else [])
                self.assertEqual(report['formal_gate'], 'NOT_CERTIFIED')
                self.assertIn(expected.encode(), result.stdout)
                self.assertIn(b'NOT_CERTIFIED', result.stdout)
                summary = (d/'out/lifecycle-summary.md').read_text(encoding='utf-8')
                self.assertIn(expected, summary); self.assertIn('NOT_CERTIFIED', summary)
                self.assertEqual(p.loads((d/'state.json').read_text(encoding='utf-8'))['schema_version'], 1)
                self.assertEqual(p.loads((d/'input.json').read_text(encoding='utf-8')), v)

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
            self.assertIn('V4.0 kit', (d/'out/owner_resume_registration.md').read_text(encoding='utf-8'))
            self.assertIn('まずWork会話へマージ確認', (d/'out/owner_resume_registration.md').read_text(encoding='utf-8'))
            self.assertIn(b'NOT_CERTIFIED',result.stdout); self.assertTrue((d/'out/owner_resume_registration.md').exists())
            self.assertEqual(p.loads((d/'state.json').read_text(encoding='utf-8'))['schema_version'],1)
