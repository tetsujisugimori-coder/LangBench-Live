"""Synthetic I-01 event/Work fixtures; no real task, merge, or dispatch."""
import base64
import copy
import json
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from tools import work_owner_resume as resume
from tools.automation_dashboard import REPOSITORY, WORK
from tests.test_automation_dashboard import record, run

ROOT = Path(__file__).resolve().parents[1]
HEAD, MERGE = 'a' * 40, 'c' * 40
T0 = '2026-10-08T00:00:00Z'
T1 = '2026-10-08T00:01:00Z'
T2 = '2026-10-08T00:02:00Z'
T3 = '2026-10-08T00:03:00Z'
URL = 'https://github.com/tetsujisugimori-coder/LangBench-Live/issues/96#issuecomment-123'


def fixture():
    policy = json.loads((ROOT / '.github/automation-dashboard.json').read_text(encoding='utf-8'))['issues']['96']
    owner = policy['owner']
    value = {'schema_version': 1, 'repository': REPOSITORY, 'issue': 96, 'purpose': resume.PURPOSE,
             'pr': 101, 'reviewed_head_sha': HEAD, 'merge_sha': MERGE, 'target_main_sha': MERGE,
             'owner': owner, 'waiting_record': {'comment_id': 123, 'body_sha256': resume.waiting_digest('waiting')},
             'event': {'delivery_id': 'synthetic-delivery', 'repository': REPOSITORY, 'pr': 101,
                       'action': 'closed', 'head_sha': HEAD, 'merge_sha': MERGE, 'evidence_url': URL, 'observed_at': T1},
             'work': {'run_id': 'synthetic-work-run', 'automation_id': 'e' * 32, 'started_at': T1,
                      'evidence_url': URL, 'observed_at': T1},
             'claim': None, 'receipt': None, 'next_action': None, 'recheck': None}
    value['claim'] = {'dedup_key': resume.key(value), 'run_id': value['work']['run_id'],
                      'owner': 'Work(root)', 'status': 'RUNNING', 'evidence_url': URL, 'observed_at': T1}
    value['receipt'] = {'run_id': value['work']['run_id'], 'waiting_comment_id': 123,
                        'waiting_body_sha256': value['waiting_record']['body_sha256'], 'evidence_url': URL, 'observed_at': T1}
    value['next_action'] = {'run_id': value['work']['run_id'], 'dedup_key': resume.key(value),
                           'kind': 'live_smoke', 'status': 'EXECUTED', 'authorization_ref': 'Issue96',
                           'evidence_url': URL, 'observed_at': T3}
    review = {'schema_version': 1, 'repository': REPOSITORY, 'issue': 96, 'pr': 101,
              'kind': 'work_review', 'automation_id': policy['work_automation_id'], 'head_sha': HEAD,
              'verdict': 'PASS', 'blockers': [], 'active_blocker': None, 'conditions': {},
              'follow_up': [], 'follow_up_recorded': True}
    sync, jobs = run(20, 'pull-local-main.yml', 2, MERGE, 'push', ['verify-merge', 'pull-main'])
    sync['updated_at'] = T2
    facts = {'main_sha': MERGE, 'policy': policy,
             'issue': {'number': 96, 'user': owner, 'body': 'purpose: work-owner-resume-i01'},
             'pr': {'number': 101, 'base': {'ref': 'main', 'repo': {'full_name': REPOSITORY}},
                    'head': {'sha': HEAD}, 'merged': True, 'merged_by': owner,
                    'merged_at': T0, 'merge_commit_sha': MERGE, 'body': 'Refs #96'},
             'issue_comments': [{'id': 123, 'user': owner, 'body': 'waiting'},
                                {'id': 124, 'user': owner, 'body': resume.CLAIM_START + json.dumps(value['claim']) + resume.CLAIM_END}],
             'pr_comments': [record(WORK, review, user=owner)],
             'sync_runs': [sync], 'jobs': {'20': jobs}, 'workflow_ids': {'pull-local-main.yml': 2},
             'sync_artifacts': {'20': {'artifact_id': 77, 'name': 'local-main-sync-20-attempt1',
                                       'digest': 'sha256:' + 'd' * 64, 'zip_verified': True, 'evidence_url': URL}},
             'sync_reports': {'20': {'schema_version': 1, 'repository': REPOSITORY, 'pr': 101,
                                     'pr_head_sha': HEAD, 'merge_sha': MERGE, 'target_sha': MERGE,
                                     'before_sha': 'b' * 40, 'after_sha': MERGE,
                                     'run_id': '20', 'run_attempt': 1, 'status': 'success',
                                     'protected_preserved': True, 'protected_files': 7124}}}
    return value, facts


class MergeObservation(unittest.TestCase):
    def test_correct_merge_is_observation_not_gate(self):
        value, facts = fixture()
        out = resume.observe(value, facts)
        self.assertEqual(out['status'], 'OBSERVED')
        self.assertEqual(out['stage'], '実動確認済み')
        self.assertFalse(out['gate_certified'])
        self.assertFalse(out['deadline_guaranteed'])
        self.assertEqual(resume.observe(value, facts, out), out)

    def test_input_scope_and_missing_fields(self):
        for field, change in [('repository', 'other/repo'), ('issue', None), ('purpose', 'phase2'),
                              ('target_main_sha', 'b' * 40), ('pr', True), ('schema_version', True)]:
            with self.subTest(field=field):
                value, facts = fixture()
                value[field] = change
                with self.assertRaises(ValueError): resume.observe(value, facts)
        value, facts = fixture()
        del value['event']['delivery_id']
        with self.assertRaises(ValueError): resume.observe(value, facts)

    def test_current_api_mismatches_and_missing_fields(self):
        mutations = [lambda f: f['pr'].update(merged=False),
                     lambda f: f['pr']['base']['repo'].update(full_name='other/repo'),
                     lambda f: f['pr']['base'].update(ref='dev'),
                     lambda f: f['issue'].update(number=99),
                     lambda f: f['issue'].update(body='purpose: other'),
                     lambda f: f['pr'].update(body='Refs #99'),
                     lambda f: f.update(main_sha='d' * 40),
                     lambda f: f['pr']['head'].update(sha='d' * 40),
                     lambda f: f['pr'].update(merge_commit_sha='d' * 40),
                     lambda f: f['pr'].pop('merged_at'),
                     lambda f: f['pr'].update(merged_by={'login': 'bot', 'id': 1, 'type': 'Bot'}),
                     lambda f: f['policy'].update(purpose='other'),
                     lambda f: f['issue_comments'][0].update(body='changed'),
                     lambda f: f['pr_comments'].clear()]
        for mutate in mutations:
            value, facts = fixture()
            mutate(facts)
            self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_failed_fetch_invalidates_prior_success(self):
        value, facts = fixture()
        prior = resume.observe(value, facts)
        self.assertEqual(resume.observe(value, {'fetch_error': True}, prior)['status'], 'STOPPED')

    def test_duplicate_work_and_shared_claim_conflict(self):
        value, facts = fixture()
        prior = resume.observe(value, facts)
        for field in ('work', 'claim', 'receipt', 'next_action'):
            value[field]['run_id'] = 'second-work'
        stopped = resume.observe(value, facts, prior)
        self.assertEqual(stopped['status'], 'STOPPED')
        self.assertEqual(stopped['claimed_run_id'], 'synthetic-work-run')
        self.assertEqual(resume.observe(value, facts, stopped)['status'], 'STOPPED')
        value, facts = fixture()
        facts['issue_comments'].append(copy.deepcopy(facts['issue_comments'][1]))
        self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')
        value, facts = fixture()
        facts['issue_comments'].pop()
        self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_unknown_failure_cancel_timeout_and_recovery(self):
        for status in ('UNKNOWN', 'FAILED', 'CANCELLED'):
            value, facts = fixture()
            value['claim']['status'] = status
            facts['issue_comments'][1]['body'] = resume.CLAIM_START + json.dumps(value['claim']) + resume.CLAIM_END
            old = resume.observe(value, facts)
            self.assertEqual(old['status'], 'STOPPED')
            value['claim']['status'] = 'RUNNING'
            value['claim']['observed_at'] = T2
            value['receipt']['observed_at'] = T2
            facts['issue_comments'][1]['body'] = resume.CLAIM_START + json.dumps(value['claim']) + resume.CLAIM_END
            self.assertEqual(resume.observe(value, facts, old)['status'], 'OBSERVED')
        value, facts = fixture()
        value['receipt'] = None  # execution ended without receipt, including timeout
        self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_sync_pending_requires_real_recheck_route(self):
        value, facts = fixture()
        facts['sync_runs'][0]['status'] = 'in_progress'
        out = resume.observe(value, facts)
        self.assertEqual(out['status'], 'WAITING')
        self.assertFalse(out['deadline_guaranteed'])
        value['recheck'] = {'id': 'synthetic-recheck', 'enabled': True, 'dedup_key': resume.key(value),
                            'run_id': value['work']['run_id'], 'stop_condition': 'sync terminal or target changed',
                            'evidence_url': URL, 'observed_at': T2}
        out = resume.observe(value, facts)
        self.assertIn('synthetic-recheck', out['next_action'])
        self.assertNotEqual(out['stage'], '実動確認済み')
        value['recheck']['enabled'] = False
        with self.assertRaises(ValueError): resume.observe(value, facts)

    def test_sync_failure_wrong_artifact_and_attempt(self):
        for mutate in [lambda f: f['sync_runs'][0].update(conclusion='failure'),
                       lambda f: f['sync_runs'][0].update(conclusion='cancelled'),
                       lambda f: f['sync_reports']['20'].update(protected_preserved=False),
                       lambda f: f['sync_reports']['20'].update(run_attempt=2),
                       lambda f: f['sync_reports']['20'].update(after_sha='b' * 40),
                       lambda f: f['sync_artifacts']['20'].update(zip_verified=False),
                       lambda f: f['sync_artifacts']['20'].update(digest='wrong'),
                       lambda f: f['sync_reports'].clear()]:
            value, facts = fixture()
            mutate(facts)
            self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_no_operation_no_live_success(self):
        for status in (None, 'UNKNOWN', 'FAILED', 'CANCELLED', 'NO_OP'):
            value, facts = fixture()
            if status is None: value['next_action'] = None
            else: value['next_action']['status'] = status
            self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_old_event_receipt_and_action(self):
        for field in ('event', 'receipt', 'next_action'):
            value, facts = fixture()
            value[field]['observed_at'] = '2026-10-07T00:00:00Z'
            self.assertEqual(resume.observe(value, facts)['status'], 'STOPPED')

    def test_rejected_late_evidence_keeps_accepted_baseline(self):
        newer, facts = fixture()
        newer['event']['observed_at'] = T2
        newer['receipt']['observed_at'] = T2
        accepted = resume.observe(newer, facts)
        self.assertEqual(accepted['status'], 'OBSERVED')
        for input_field, output_field, late_time in (
                ('event', 'event', T1), ('receipt', 'receipt', T1),
                ('next_action', 'action', T2)):
            with self.subTest(field=input_field):
                late = copy.deepcopy(newer)
                late[input_field]['observed_at'] = late_time
                stopped = resume.observe(late, facts, accepted)
                self.assertEqual(stopped['status'], 'STOPPED')
                self.assertEqual(stopped[output_field], accepted[output_field])
                repeated = resume.observe(late, facts, stopped)
                self.assertEqual(repeated['status'], 'STOPPED')
                self.assertEqual(repeated[output_field], accepted[output_field])

    def test_saved_late_evidence_cannot_be_promoted_on_repeat(self):
        for field in ('event', 'receipt', 'next_action'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                value, facts = fixture()
                value[field]['observed_at'] = T3
                if field == 'receipt': value['next_action']['observed_at'] = T3
                accepted = resume.observe(value, facts)
                self.assertEqual(accepted['status'], 'OBSERVED')
                value[field]['observed_at'] = '2026-10-08T00:02:30Z'
                rejected = resume.observe(value, facts, accepted)
                self.assertEqual(rejected['status'], 'STOPPED')
                history_field = 'action' if field == 'next_action' else field
                self.assertEqual(rejected['evidence_history'][history_field]['observed_at'], T3)
                path = Path(directory) / 'state.json'
                resume.save_observation(path, rejected)
                restored = resume.preparation.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(resume.observe(value, facts, restored)['status'], 'STOPPED')

    def test_newer_negative_and_equal_time_conflict_survive_reobservation(self):
        value, facts = fixture()
        accepted = resume.observe(value, facts)
        negative = copy.deepcopy(value)
        negative['next_action'].update(status='FAILED', observed_at='2026-10-08T00:04:00Z')
        stopped = resume.observe(negative, facts, accepted)
        self.assertEqual(stopped['status'], 'STOPPED')
        self.assertEqual(stopped['evidence_history']['action']['status'], 'FAILED')
        for _ in range(2):
            stopped = resume.observe(value, facts, stopped)
            self.assertEqual(stopped['status'], 'STOPPED')
        changed = copy.deepcopy(value)
        changed['next_action']['status'] = 'FAILED'  # Same-time conflicting observations need fresh proof.
        conflict = resume.observe(changed, facts, accepted)
        self.assertEqual(conflict['status'], 'STOPPED')
        self.assertEqual(resume.observe(value, facts, conflict)['status'], 'STOPPED')
        value['next_action']['observed_at'] = '2026-10-08T00:05:00Z'
        self.assertEqual(resume.observe(value, facts, conflict)['status'], 'OBSERVED')

    def test_non_temporal_stops_preserve_all_evidence_high_water(self):
        for failure in ('api', 'missing_action', 'unknown_action'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                value, facts = fixture()
                value['event']['observed_at'] = T3
                value['receipt']['observed_at'] = T3
                accepted = resume.observe(value, facts)
                attempt = copy.deepcopy(value)
                if failure == 'api':
                    attempt['next_action']['observed_at'] = '2026-10-08T00:02:30Z'
                    stopped = resume.observe(attempt, {'fetch_error': True}, accepted)
                else:
                    if failure == 'missing_action': attempt['next_action'] = None
                    else: attempt['next_action']['status'] = 'UNKNOWN'
                    stopped = resume.observe(attempt, facts, accepted)
                self.assertEqual(stopped['status'], 'STOPPED')
                path = Path(directory) / 'state.json'
                resume.save_observation(path, stopped)
                prior = resume.preparation.loads(path.read_text(encoding='utf-8'))
                late = copy.deepcopy(value)
                late['event']['observed_at'] = T2
                late['receipt']['observed_at'] = T2
                late['next_action']['observed_at'] = '2026-10-08T00:02:30Z'
                for _ in range(2):
                    prior = resume.observe(late, facts, prior)
                    self.assertEqual(prior['status'], 'STOPPED')
                    for field in ('event', 'receipt', 'action'):
                        self.assertEqual(prior['evidence_history'][field]['observed_at'], T3)
                    resume.save_observation(path, prior)
                    prior = resume.preparation.loads(path.read_text(encoding='utf-8'))

    def test_cli_missing_action_does_not_erase_accepted_evidence(self):
        value, facts = fixture()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'facts.json').write_text(json.dumps(facts), encoding='utf-8')
            args = [sys.executable, '-B', 'tools/work_owner_resume.py', '--handoff', str(folder / 'handoff.json'),
                    '--state', str(folder / 'state.json'), '--fixture-facts', str(folder / 'facts.json')]
            for action, expected in ((value['next_action'], 0), (None, 1),
                                     ({**value['next_action'], 'observed_at': '2026-10-08T00:02:30Z'}, 1)):
                current = {**value, 'next_action': action}
                (folder / 'handoff.json').write_text(json.dumps(current), encoding='utf-8')
                result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, expected, result.stderr)
                saved = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['evidence_history']['action']['observed_at'], T3)

    def test_mixed_stale_and_newer_negative_fields_update_before_stop(self):
        value, facts = fixture()
        accepted = resume.observe(value, facts)
        mixed = copy.deepcopy(value)
        mixed['event']['observed_at'] = '2026-10-08T00:00:30Z'
        mixed['next_action'].update(status='FAILED', observed_at='2026-10-08T00:04:00Z')
        stopped = resume.observe(mixed, facts, accepted)
        self.assertEqual(stopped['status'], 'STOPPED')
        self.assertEqual(stopped['evidence_history']['action']['status'], 'FAILED')
        self.assertEqual(resume.observe(value, facts, stopped)['status'], 'STOPPED')

        value, facts = fixture()
        accepted = resume.observe(value, facts)
        mixed = copy.deepcopy(value)
        mixed['claim'].update(status='FAILED', observed_at=T2)
        mixed['receipt']['observed_at'] = T2
        mixed['next_action']['observed_at'] = T2
        facts['issue_comments'][1]['body'] = resume.CLAIM_START + json.dumps(mixed['claim']) + resume.CLAIM_END
        stopped = resume.observe(mixed, facts, accepted)
        self.assertEqual(stopped['status'], 'STOPPED')
        self.assertEqual(stopped['evidence_history']['claim']['status'], 'FAILED')
        replay, replay_facts = fixture()
        self.assertEqual(resume.observe(replay, replay_facts, stopped)['status'], 'STOPPED')

    def test_mixed_negative_and_stale_fields_survive_persisted_replay(self):
        for negative_field in ('claim', 'next_action'):
            for status in ('FAILED', 'UNKNOWN', 'CANCELLED'):
                for failure in ('mixed', 'api', 'missing_receipt'):
                    with self.subTest(field=negative_field, status=status, failure=failure), tempfile.TemporaryDirectory() as directory:
                        original, facts = fixture()
                        accepted = resume.observe(original, facts)
                        mixed, current_facts = copy.deepcopy(original), copy.deepcopy(facts)
                        mixed[negative_field].update(status=status, observed_at='2026-10-08T00:04:00Z')
                        if negative_field == 'next_action':
                            mixed['event']['observed_at'] = '2026-10-08T00:00:30Z'
                        else:
                            mixed['next_action']['observed_at'] = '2026-10-08T00:02:30Z'
                            current_facts['issue_comments'][1]['body'] = resume.CLAIM_START + json.dumps(mixed['claim']) + resume.CLAIM_END
                        if failure == 'api': current_facts = {'fetch_error': True}
                        elif failure == 'missing_receipt': mixed['receipt'] = None
                        stopped = resume.observe(mixed, current_facts, accepted)
                        self.assertEqual(stopped['status'], 'STOPPED')
                        field = 'action' if negative_field == 'next_action' else negative_field
                        self.assertEqual(stopped['evidence_history'][field]['status'], status)
                        path = Path(directory) / 'state.json'
                        for _ in range(2):
                            resume.save_observation(path, stopped)
                            restored = resume.preparation.loads(path.read_text(encoding='utf-8'))
                            stopped = resume.observe(original, facts, restored)
                            self.assertEqual(stopped['status'], 'STOPPED')
                            self.assertEqual(stopped['evidence_history'][field]['status'], status)

    def test_mixed_same_time_conflict_retains_later_negative(self):
        original, facts = fixture()
        accepted = resume.observe(original, facts)
        mixed = copy.deepcopy(original)
        mixed['event']['delivery_id'] = 'conflicting-at-same-time'
        mixed['next_action'].update(status='FAILED', observed_at='2026-10-08T00:04:00Z')
        stopped = resume.observe(mixed, facts, accepted)
        self.assertEqual(stopped['status'], 'STOPPED')
        self.assertEqual(stopped['evidence_history']['action']['status'], 'FAILED')
        self.assertEqual(resume.observe(original, facts, stopped)['status'], 'STOPPED')
        original['event']['observed_at'] = T2
        original['next_action']['observed_at'] = '2026-10-08T00:05:00Z'
        self.assertEqual(resume.observe(original, facts, stopped)['status'], 'OBSERVED')

    def test_cli_mixed_newer_failure_blocks_old_positive_replay(self):
        original, facts = fixture()
        mixed = copy.deepcopy(original)
        mixed['event']['observed_at'] = '2026-10-08T00:00:30Z'
        mixed['next_action'].update(status='FAILED', observed_at='2026-10-08T00:04:00Z')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'facts.json').write_text(json.dumps(facts), encoding='utf-8')
            args = [sys.executable, '-B', 'tools/work_owner_resume.py', '--handoff', str(folder / 'handoff.json'),
                    '--state', str(folder / 'state.json'), '--fixture-facts', str(folder / 'facts.json')]
            for value, expected in ((original, 0), (mixed, 1), (original, 1), (original, 1)):
                (folder / 'handoff.json').write_text(json.dumps(value), encoding='utf-8')
                result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, expected, result.stderr)
            saved = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['evidence_history']['action']['status'], 'FAILED')

    def test_read_adapter_reuses_current_policy_and_sync(self):
        value, facts = fixture()
        class API:
            def get(self, path):
                if path == '/branches/main': return {'commit': {'sha': MERGE}}
                if path.startswith('/contents/'):
                    return {'content': base64.b64encode(json.dumps({'issues': {'96': facts['policy']}}).encode()).decode()}
                if path == '/issues/96': return facts['issue']
                raise AssertionError(path)
        with patch.object(resume, 'collect', return_value=(None, copy.deepcopy(facts))) as collect:
            self.assertEqual(resume.read_facts(API(), value)['main_sha'], MERGE)
            self.assertEqual(collect.call_args.args[3]['pr'], 101)

    def test_real_collection_and_zip_digest_transport(self):
        value, facts = fixture()
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('sync-report.json', json.dumps(facts['sync_reports']['20']))
        data = archive.getvalue()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        workflows = [{'id': index, 'state': 'active', 'path': '.github/workflows/' + name}
                     for index, name in enumerate(['python-tests.yml', 'pull-local-main.yml',
                                                   'measurement-validation-windows.yml', 'function-call-analysis-windows.yml'], 1)]
        calls = []
        def transport(api, path, method='GET', body=None, raw=False):
            calls.append((method, path))
            self.assertEqual(method, 'GET')
            suffix = path.removeprefix(api.root).split('?')[0]
            routes = {'/branches/main': {'commit': {'sha': MERGE}},
                      '/contents/.github/automation-dashboard.json': {'content': base64.b64encode(json.dumps({'issues': {'96': facts['policy']}}).encode()).decode()},
                      '/issues/96': facts['issue'], '/issues/96/comments': facts['issue_comments'],
                      '/pulls/101': facts['pr'], '/issues/101/comments': facts['pr_comments'],
                      '/pulls/101/reviews': [], '/actions/workflows': {'workflows': workflows},
                      '/actions/workflows/python-tests.yml/runs': {'workflow_runs': []},
                      '/actions/workflows/pull-local-main.yml/runs': {'workflow_runs': facts['sync_runs']},
                      '/actions/runs/20/attempts/1/jobs': {'jobs': facts['jobs']['20']},
                      '/actions/runs/20/artifacts': {'artifacts': [{'id': 77, 'name': 'local-main-sync-20-attempt1', 'expired': False, 'digest': digest}]},
                      '/actions/artifacts/77/zip': data}
            return copy.deepcopy(routes[suffix])
        with patch.object(resume.GitHub, 'request', transport):
            api = resume.ObservationGitHub('synthetic-token')
            observed = resume.read_facts(api, value)
            self.assertEqual(resume.observe(value, observed)['status'], 'OBSERVED')
            self.assertEqual(observed['sync_artifacts']['20']['digest'], digest)
            self.assertTrue(any(path.endswith('/zip') for _, path in calls))
            with self.assertRaises(ValueError): api.request(api.root + '/issues/96/comments', 'POST')
            # Actual corrupt ZIP bytes, not a forged boolean fixture.
            data += b'corruption'
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                resume.read_facts(api, value)

    def test_atomic_write_failure_preserves_prior(self):
        value, facts = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            resume.save_observation(path, resume.observe(value, facts))
            before = path.read_bytes()
            with patch.object(resume.os, 'replace', side_effect=OSError('interruption')):
                with self.assertRaises(OSError): resume.save_observation(path, {'bad': 'new'})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_documented_cli_subprocess_and_no_op(self):
        value, facts = fixture()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'handoff.json').write_text(json.dumps(value), encoding='utf-8')
            (folder / 'facts.json').write_text(json.dumps(facts), encoding='utf-8')
            args = [sys.executable, '-B', 'tools/work_owner_resume.py', '--handoff', str(folder / 'handoff.json'),
                    '--state', str(folder / 'state.json'), '--fixture-facts', str(folder / 'facts.json')]
            first = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(first.returncode, 0, first.stderr)
            out = json.loads(first.stdout)
            self.assertEqual(out['status'], 'FIXTURE_ONLY')
            self.assertEqual(out['stage'], '実装済み')
            stamp = (folder / 'state.json').stat().st_mtime_ns
            again = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn('NO_OP', again.stdout)
            self.assertEqual((folder / 'state.json').stat().st_mtime_ns, stamp)
            value['next_action']['observed_at'] = T2
            (folder / 'handoff.json').write_text(json.dumps(value), encoding='utf-8')
            late = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(late.returncode, 1)
            saved = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['action']['observed_at'], T3)
            repeated = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(repeated.returncode, 1)
            self.assertEqual(json.loads((folder / 'state.json').read_text(encoding='utf-8'))['action']['observed_at'], T3)
            value['next_action']['observed_at'] = '2026-10-08T00:02:30Z'
            (folder / 'handoff.json').write_text(json.dumps(value), encoding='utf-8')
            for _ in range(2):
                late = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
                self.assertEqual(late.returncode, 1, late.stderr)
                saved = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['status'], 'STOPPED')
                self.assertEqual(saved['evidence_history']['action']['observed_at'], T3)
            facts['pr']['merged'] = False
            (folder / 'facts.json').write_text(json.dumps(facts), encoding='utf-8')
            failed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding='utf-8')
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads((folder / 'state.json').read_text(encoding='utf-8'))['status'], 'STOPPED')


if __name__ == '__main__':
    unittest.main()
