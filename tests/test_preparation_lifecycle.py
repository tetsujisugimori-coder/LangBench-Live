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
    def observation_rows(self, report):
        return {parts[0]: parts[1:] for line in l.observability(report).splitlines()
                if line.startswith('| ') and (parts := [s.strip() for s in line.strip('|').split('|')])}

    def test_observability_does_not_promote_complete_local_evidence(self):
        v, r = self.complete_fixture('FINISHED')
        report = l.assess(v, r)
        before = copy.deepcopy(report)
        rows = self.observation_rows(report)
        self.assertEqual(report['status'], 'PHASE_EVIDENCE_COMPLETE')
        for stage in ('candidate_generation', 'review.work_start', 'review.target_match',
                      'review.result_post', 'owner_resume.work_start', 'owner_resume.target_match',
                      'owner_resume.waiting', 'human_merge', 'windows_sync', 'result_saved'):
            with self.subTest(stage=stage):
                self.assertEqual(rows[stage][0], 'unverified')
        for role in ('review', 'owner_resume'):
            for stage in ('registration', 'settings_readback', 'event', 'stop_readback'):
                self.assertEqual(rows[role + '.' + stage][0], 'confirmed')
        self.assertEqual(report, before)
        self.assertEqual(report['formal_gate'], 'NOT_CERTIFIED')

    def test_observability_missing_failed_unknown_and_enabled_are_not_stopped(self):
        for status in l.STATUSES - {'DISABLED_CONFIRMED'}:
            v, r = fixture('PRE_MERGE')
            for role in ('review', 'owner_resume'):
                r[role].update(status=status, settings_verified=status == 'SETTINGS_CONFIRMED',
                               event_verified=False)
            r['execution'] = {k: None for k in l.EXEC_FIELDS}
            report = l.assess(v, r)
            rows = self.observation_rows(report)
            for role in ('review', 'owner_resume'):
                self.assertEqual(rows[role + '.stop_readback'][0], 'unverified')
                self.assertEqual(rows[role + '.work_start'][0], 'unverified')
                self.assertEqual(rows[role + '.event'][0], 'unverified')
                if status == 'FAILED':
                    self.assertEqual(rows[role + '.registration'][0], 'failed')
            # A post failure cannot be encoded in legacy fields; absence must never mean success.
            self.assertEqual(rows['review.result_post'][0], 'unverified')
            self.assertEqual(rows['result_saved'][0], 'unverified')

    def test_observability_current_negative_does_not_inherit_history(self):
        v, old = self.complete_fixture('POST_MERGE')
        r = copy.deepcopy(old)
        r['observed_at'] = '2026-10-08T03:01:00Z'
        r['review'].update(status='UNKNOWN', enabled=None, settings_verified=False, event_verified=False)
        r['execution'] = {k: None for k in l.EXEC_FIELDS}
        report = l.assess(v, r, l.assess(v, old))
        rows = self.observation_rows(report)
        for stage in ('review.registration', 'review.settings_readback', 'review.event',
                      'review.stop_readback', 'windows_sync', 'result_saved'):
            self.assertEqual(rows[stage][0], 'unverified')
        self.assertEqual(len(report['history']), 1)

    def test_observability_keeps_untrusted_references_inside_table_cells(self):
        v, r = fixture()
        r['review']['evidence_ref'] = 'https://example.test/a|b\n<script>fake</script>'
        text = l.summary(l.assess(v, r))
        self.assertIn('a&#124;b &lt;script&gt;fake&lt;/script&gt;', text)
        self.assertNotIn('<script>', text)

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

    def sequence_fixture(self):
        v, r = self.complete_fixture('PRE_MERGE')
        r['owner_resume'].update(status='NOT_ATTEMPTED', id=None, enabled=None,
                                 settings_verified=False)
        checks = dict(input_digest=p.digest(v), pr=r['pr'], head_sha='d'*40,
                      review_id=r['review']['id'], observed_at=r['observed_at'],
                      independent_review_accepted=True, required_ci_passed=True,
                      publication_matched=True, review_result_ref='synthetic://result',
                      ci_ref='synthetic://ci', publication_ref='synthetic://publication',
                      stop_update_ref='synthetic://update', stop_peek_ref='synthetic://peek',
                      stop_update_at='2026-10-08T02:58:00Z',
                      stop_peek_at='2026-10-08T02:59:00Z', stop_peek_enabled=False)
        return v, r, checks

    def sequence(self, v, r, checks):
        return p.owner_registration_sequence(v, l.assess(v, r), checks, 99, 'd'*40)

    def test_sequential_candidate_requires_all_current_evidence(self):
        v, r, c = self.sequence_fixture()
        original = copy.deepcopy((v, r, c))
        self.assertTrue(self.sequence(v, r, c).startswith('CANDIDATE_ONLY:'))
        self.assertEqual((v, r, c), original)
        self.assertEqual(l.assess(v, r)['status'], 'WAITING')
        self.assertEqual(l.assess(v, r)['formal_gate'], 'NOT_CERTIFIED')
        for key, invalid in (('independent_review_accepted', False), ('required_ci_passed', False),
                             ('publication_matched', False), ('review_result_ref', None),
                             ('stop_peek_ref', None), ('stop_peek_enabled', None),
                             ('stop_peek_enabled', True), ('head_sha', 'e'*40),
                             ('pr', 100), ('input_digest', 'f'*64), ('review_id', 'b'*32),
                             ('observed_at', '2026-10-08T02:59:00Z'),
                             ('stop_peek_at', '2026-10-08T02:57:00Z'),
                             ('stop_peek_at', '2026-10-08T03:01:00Z'),
                             ('stop_update_at', 'invalid'), ('stop_peek_ref', 'synthetic://update')):
            with self.subTest(key=key, invalid=invalid):
                changed = copy.deepcopy(c); changed[key] = invalid
                self.assertTrue(self.sequence(v, r, changed).startswith('WAIT:'))
        self.assertTrue(self.sequence(v, r, None).startswith('WAIT:'))
        self.assertTrue(p.owner_registration_sequence(v, l.assess(v, r), c).startswith('WAIT:'))

    def test_sequential_unstopped_unknown_or_unverified_review_waits(self):
        for status in ('SETTINGS_CONFIRMED', 'REGISTERED', 'UNKNOWN', 'ATTEMPTING',
                       'NOT_ATTEMPTED', 'FAILED'):
            with self.subTest(status=status):
                v, r, c = self.sequence_fixture()
                r['review'].update(status=status, enabled=True,
                                   settings_verified=status == 'SETTINGS_CONFIRMED')
                self.assertTrue(self.sequence(v, r, c).startswith('WAIT:'))
        v, r, c = self.sequence_fixture(); r['review']['event_verified'] = False
        self.assertTrue(self.sequence(v, r, c).startswith('WAIT:'))

    def test_sequential_owner_history_never_prompts_new_registration(self):
        for status in l.STATUSES - {'NOT_ATTEMPTED'}:
            with self.subTest(status=status):
                v, r, c = self.sequence_fixture()
                r['owner_resume'].update(status=status, id='b'*32,
                    settings_verified=status in ('SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'),
                    enabled=status != 'DISABLED_CONFIRMED')
                before = copy.deepcopy(r)
                self.assertTrue(self.sequence(v, r, c).startswith('RECONCILE_ONLY:'))
                self.assertEqual(r, before)
        v, r, c = self.sequence_fixture()
        r['owner_resume'].update(status='UNKNOWN')
        self.assertTrue(self.sequence(v, r, c).startswith('RECONCILE_ONLY:'))

    def test_sequential_new_empty_owner_cannot_hide_registered_or_unknown_history(self):
        for status, task_id in (('SETTINGS_CONFIRMED', 'b'*32), ('UNKNOWN', None)):
            with self.subTest(status=status):
                v, r, c = self.sequence_fixture()
                prior = copy.deepcopy(r)
                prior['owner_resume'].update(status=status, id=task_id,
                    settings_verified=status == 'SETTINGS_CONFIRMED',
                    enabled=status == 'SETTINGS_CONFIRMED')
                old_report = l.assess(v, prior)
                r['observed_at'] = '2026-10-08T03:01:00Z'
                c['observed_at'] = r['observed_at']
                report = l.assess(v, r, old_report)
                self.assertTrue(p.owner_registration_sequence(v, report, c, 99, 'd'*40)
                                .startswith('RECONCILE_ONLY:'))

    def test_cli_sequential_wait_candidate_and_stale_checks(self):
        v, r, c = self.sequence_fixture()
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            (d/'input.json').write_text(p.canonical(v), encoding='utf-8')
            (d/'phase.json').write_text(p.canonical(r), encoding='utf-8')
            cmd = [sys.executable, '-B', str(root/'tools/startup_preparation.py'),
                   '--input', str(d/'input.json'), '--state', str(d/'state.json'),
                   '--output', str(d/'out'), '--config', str(root/'.github/automation-dashboard.json'),
                   '--lifecycle', str(d/'phase.json'), '--review-pr', '99', '--review-head', 'd'*40]
            for checks, expected in ((None, 'WAIT:'), (c, 'CANDIDATE_ONLY:'),
                                    ({**c, 'head_sha': 'e'*40}, 'WAIT:')):
                args = []
                if checks is not None:
                    (d/'checks.json').write_text(p.canonical(checks), encoding='utf-8')
                    args = ['--owner-registration-checks', str(d/'checks.json')]
                subprocess.run(cmd + args, check=True, capture_output=True, cwd=root)
                text = (d/'out/owner_resume_registration.md').read_text(encoding='utf-8')
                self.assertIn(expected, text)
                self.assertNotIn('Actual PR known -> register owner-resume', text)
                self.assertIn('今回実行の固定role=owner_resume。', text)
                self.assertIn('NOT_CERTIFIED', (d/'out/lifecycle-assessment.json').read_text())

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
                self.assertIn('Work lifecycle observations (local assertions)', summary)
                self.assertIn('| review.result_post | unverified |', summary)
                self.assertIn('| windows_sync | unverified |', summary)
                owner_prompt = (d/'out/owner_resume_registration.md').read_text(encoding='utf-8')
                self.assertIn('今回実行の固定role=owner_resume。', owner_prompt)
                self.assertNotIn('今回実行の固定role=review。', owner_prompt)
                self.assertIn('reviewのclosed NO_OPでowner_resumeのmerge後処理を打ち切らない', owner_prompt)
                self.assertIn('owner_resumeは独立review結果を代筆しない', owner_prompt)
                self.assertIn('別task IDや同一親conversation IDだけで実行分離を認定しない', owner_prompt)
                self.assertIn('「投稿開始」', owner_prompt)
                self.assertIn('「読戻し確認」', owner_prompt)
                self.assertIn('人間merge前にreviewだけ停止読戻し', owner_prompt)
                self.assertIn('結果保存・読戻しの後にowner_resumeを停止読戻し', owner_prompt)
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
