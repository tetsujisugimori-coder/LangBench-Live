"""Issue #85 registration/lifecycle regression fixtures (no external runs)."""
import copy
import json
import subprocess
import unittest

from tools.automation_dashboard import (RECEIPT, WORK, dedup_key, evaluate,
                                        initial_state, parse_state, render, valid_receipt)
from tools.update_automation_dashboard import collect, reconcile, references, safe_stop
from tests.test_automation_dashboard import FakeGitHub, HEAD, OLD, NOW, ROOT, fixtures, record


def issue85_fixture():
    policy = json.loads((ROOT / '.github/automation-dashboard.json').read_text())['issues']['85']
    _, facts, report = fixtures()
    report.update(issue=85, pr=86, automation_id=policy['work_automation_id'])
    facts['pr'].update(number=86, title='Issue #85: Summary-only', body=f'Refs #85\nCurrent head: {HEAD}\n')
    facts['pr_comments'] = [record(WORK, report)]
    facts['ci_runs'][0]['pull_requests'] = [{'number': 86}]
    facts['dashboard_comment_id'] = None
    receipt = {'target_sha': HEAD, 'action_type': 'implementation_task',
               'purpose_id': policy['purpose'], 'state': 'SUCCEEDED',
               'run_id': 'synthetic-implementation-85', 'attempt': 1, 'retry_of': None}
    receipt['dedup_key'] = dedup_key(85, receipt)
    return policy, facts, report, receipt


def dispatch_comment(receipt, **extra):
    return record(RECEIPT, {'schema_version': 1, 'repository': 'tetsujisugimori-coder/LangBench-Live',
                           'issue': 85, 'active': True, 'dispatch': receipt, **extra})


class Issue85API(FakeGitHub):
    def request(self, path, method='GET', data=None, raw=False):
        # Retain the real collect/reconcile protocol with distinct Issue/PR IDs.
        path = path.replace('/issues/85', '/issues/80').replace('/issues/86', '/issues/81')
        path = path.replace('/pulls/86', '/pulls/81')
        return super().request(path, method, data, raw)


class Policy85Registration(unittest.TestCase):
    def setUp(self):
        self.policy, self.facts, self.report, self.receipt = issue85_fixture()

    def test_policy_identity_requirements_and_80_unchanged(self):
        config = json.loads((ROOT / '.github/automation-dashboard.json').read_text())
        original = json.loads(subprocess.check_output(
            ['git', 'show', 'b1415e0e2d649c11de160662f044123d61820921:.github/automation-dashboard.json'],
            cwd=ROOT, text=True))
        self.assertEqual(original['issues']['80'], config['issues']['80'])
        self.assertEqual({'80', '85'}, set(config['issues']))
        self.assertEqual('archive-samples-summary-only', self.policy['purpose'])
        self.assertEqual({'login': 'tetsujisugimori-coder', 'id': 265440097, 'type': 'User'}, self.policy['owner'])
        self.assertEqual(self.policy['owner'], self.policy['work_author'])
        self.assertEqual('6ac53eb50b2481918033960988ac8834', self.policy['work_automation_id'])
        self.assertNotEqual(config['issues']['80']['work_automation_id'], self.policy['work_automation_id'])
        self.assertIsNone(self.policy['initial_dispatch'])
        self.assertIsNone(self.policy['dashboard_comment_id'])
        self.assertEqual('.github/workflows/pull-local-main.yml', self.policy['dispatch_owners']['local_main_sync'])
        self.assertEqual({'windows_validation': 'NOT_REQUIRED', 'windows_measurement': 'NOT_REQUIRED',
                          'artifact_integrity': 'NOT_REQUIRED', 'measurement_result_pr': 'NOT_REQUIRED',
                          'live_smoke': 'REQUIRED'}, self.policy['requirements'])

    def test_armed_state_roundtrip_and_no_gate_pass(self):
        self.facts['pr'] = None
        state = evaluate(85, self.policy, None, self.facts)
        self.assertEqual('AUTOMATION_ARMED', state['current_state'])
        self.assertEqual([], state['dispatches'])
        for key in ('active_action', 'purpose_id', 'dedup_key', 'dispatch_state', 'active_run_id'):
            self.assertIsNone(state[key])
        self.assertEqual('PENDING', state['merge_gate']['status'])
        self.assertEqual('PENDING', state['completion_gate']['status'])
        self.assertEqual(state, parse_state(render(state), 85, self.policy))
        self.assertEqual(state, evaluate(85, self.policy, state, self.facts))
        self.assertIn('policy登録済み・実装は未起動', render(state))

    def test_writer_creates_same_dashboard_and_noop_before_dispatch(self):
        self.facts['pr'] = None
        api = Issue85API(self.policy, self.facts, None)
        self.assertEqual('UPDATED', reconcile(api, 85, self.policy, NOW))
        self.assertEqual('AUTOMATION_ARMED', parse_state(api.dashboard['body'], 85, self.policy)['current_state'])
        self.assertEqual('NO_OP', reconcile(api, 85, self.policy, NOW))
        self.assertEqual(1, len(api.writes))
        safe_stop(api, 85, self.policy)
        self.assertEqual('SAFE_STOPPED', parse_state(api.dashboard['body'], 85, self.policy)['current_state'])
        self.assertEqual('UPDATED', reconcile(api, 85, self.policy, NOW))
        self.assertEqual('AUTOMATION_ARMED', parse_state(api.dashboard['body'], 85, self.policy)['current_state'])

    def test_first_authenticated_active_receipt_transitions_and_survives_roundtrip(self):
        self.facts.update(pr=None, issue_comments=[dispatch_comment(self.receipt)])
        state = evaluate(85, self.policy, None, self.facts)
        self.assertEqual('IMPLEMENTING', state['current_state'])
        self.assertEqual(self.receipt['run_id'], state['active_run_id'])
        self.assertEqual([self.receipt], state['dispatches'])
        self.assertEqual(state, parse_state(render(state), 85, self.policy))
        self.assertEqual(state, evaluate(85, self.policy, state, self.facts))

    def test_ready_requires_dispatch_and_current_work_ci(self):
        # Even fully successful PR evidence cannot bypass the first dispatch.
        state = evaluate(85, self.policy, None, self.facts)
        self.assertEqual('SAFE_STOPPED', state['current_state'])
        self.assertEqual('BLOCKED', state['merge_gate']['status'])
        self.assertIsNone(state['pr'])
        self.assertEqual(state, parse_state(render(state), 85, self.policy))
        self.facts['issue_comments'] = [dispatch_comment(self.receipt)]
        state = evaluate(85, self.policy, state, self.facts)
        self.assertEqual('READY_FOR_HUMAN_MERGE', state['current_state'])
        self.assertEqual('PASS', state['merge_gate']['status'])
        self.assertEqual('PENDING', state['completion_gate']['status'])

    def test_unauthorized_and_other_issue_receipts_do_not_start(self):
        self.facts['pr'] = None
        for mutation in ('author', 'issue', 'repository'):
            with self.subTest(mutation=mutation):
                comment = dispatch_comment(self.receipt)
                if mutation == 'author':
                    comment['user'] = {'login': 'other', 'id': 1, 'type': 'User'}
                else:
                    value = json.loads(comment['body'].split('\n')[1])
                    value[mutation] = 86 if mutation == 'issue' else 'other/repo'
                    comment = record(RECEIPT, value)
                self.facts['issue_comments'] = [comment]
                self.assertEqual('AUTOMATION_ARMED', evaluate(85, self.policy, None, self.facts)['current_state'])

    def test_missing_initial_dispatch_does_not_default_to_unstarted(self):
        del self.policy['initial_dispatch']
        with self.assertRaises(KeyError):
            initial_state(85, self.policy)

    def test_inactive_receipt_cannot_bootstrap_active_identity(self):
        self.facts['issue_comments'] = [dispatch_comment(self.receipt, active=False)]
        with self.assertRaises(ValueError):
            evaluate(85, self.policy, None, self.facts)

    def test_no_run_id_and_invalid_dedup_fail_closed(self):
        for field, value in (('run_id', None), ('run_id', ''), ('dedup_key', 'other'), ('attempt', 0)):
            with self.subTest(field=field, value=value):
                receipt = {**self.receipt, field: value}
                self.assertFalse(valid_receipt(85, self.policy, receipt))
                self.facts['issue_comments'] = [dispatch_comment(receipt)]
                with self.assertRaises(ValueError):
                    evaluate(85, self.policy, None, self.facts)

    def test_partial_unstarted_identity_bound_pr_and_cached_pass_rejected(self):
        state = initial_state(85, self.policy)
        for key, value in (('active_action', 'implementation_task'), ('dispatch_state', 'UNKNOWN'),
                           ('active_run_id', 'placeholder'), ('pr', 86), ('head_sha', HEAD),
                           ('current_state', 'IMPLEMENTING'), ('merge_state', 'MERGED')):
            with self.subTest(key=key):
                changed = {**state, key: value}
                with self.assertRaises(ValueError):
                    parse_state(render(changed), 85, self.policy)
        for key in ('merge_gate', 'completion_gate', 'required_ci', 'work_review'):
            changed = copy.deepcopy(state)
            changed[key]['status'] = 'PASS'
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_state(render(changed), 85, self.policy)
        started = evaluate(85, self.policy, None, {**self.facts, 'issue_comments': [dispatch_comment(self.receipt)]})
        started['dispatches'] = []
        with self.assertRaises(ValueError):
            parse_state(render(started), 85, self.policy)

    def test_requested_failed_cancelled_unknown_do_not_claim_started(self):
        self.facts['pr'] = None
        for status in ('REQUESTED', 'DISPATCHING', 'UNKNOWN', 'FAILED', 'CANCELLED'):
            with self.subTest(status=status):
                self.facts['issue_comments'] = [dispatch_comment({**self.receipt, 'state': status})]
                state = evaluate(85, self.policy, None, self.facts)
                self.assertEqual('SAFE_STOPPED', state['current_state'])
                self.assertNotEqual('PASS', state['merge_gate']['status'])
                self.assertEqual(state, parse_state(render(state), 85, self.policy))

    def test_failed_or_cancelled_initial_dispatch_blocks_successful_linked_pr(self):
        for status in ('FAILED', 'CANCELLED'):
            with self.subTest(status=status):
                self.facts['issue_comments'] = [dispatch_comment({**self.receipt, 'state': status})]
                state = evaluate(85, self.policy, None, self.facts)
                self.assertEqual('BLOCKED', state['merge_gate']['status'])
                self.assertNotEqual('READY_FOR_HUMAN_MERGE', state['current_state'])

    def test_other_action_or_purpose_cannot_bootstrap_writer(self):
        for action, purpose in (('work_review', 'review'), ('local_main_sync', 'sync'),
                                ('implementation_task', 'unrelated-preparation')):
            for linked in (False, True):
                with self.subTest(action=action, linked=linked):
                    receipt = {**self.receipt, 'action_type': action, 'purpose_id': purpose}
                    receipt['dedup_key'] = dedup_key(85, receipt)
                    facts = {**self.facts, 'issue_comments': [dispatch_comment(receipt)],
                             'pr': self.facts['pr'] if linked else None}
                    api = Issue85API(self.policy, facts, render(initial_state(85, self.policy)))
                    with self.assertRaises(ValueError):
                        reconcile(api, 85, self.policy, NOW)
                    safe_stop(api, 85, self.policy)
                    state = parse_state(api.dashboard['body'], 85, self.policy)
                    self.assertEqual('SAFE_STOPPED', state['current_state'])
                    self.assertNotEqual('PASS', state['merge_gate']['status'])
                    self.assertIsNone(state['active_run_id'])
                    self.assertIsNone(state['pr'])

    def test_initial_failure_survives_other_action_and_valid_retry_recovers_writer(self):
        for status in ('FAILED', 'CANCELLED', 'REQUESTED', 'UNKNOWN'):
            with self.subTest(status=status):
                implementation = {**self.receipt, 'state': status}
                review = {**self.receipt, 'action_type': 'work_review', 'purpose_id': 'independent-review',
                          'run_id': 'synthetic-review-85'}
                review['dedup_key'] = dedup_key(85, review)
                first = dispatch_comment(implementation)
                second = dispatch_comment(review)
                first['id'], second['id'] = 100, 101
                facts = {**self.facts, 'issue_comments': [first, second]}
                api = Issue85API(self.policy, facts, None)
                self.assertEqual('UPDATED', reconcile(api, 85, self.policy, NOW))
                state = parse_state(api.dashboard['body'], 85, self.policy)
                self.assertEqual('BLOCKED', state['merge_gate']['status'])
                self.assertEqual('NO_OP', reconcile(api, 85, self.policy, NOW))
                if status not in ('FAILED', 'CANCELLED'):
                    continue
                retry = {**self.receipt, 'run_id': 'synthetic-retry-85', 'attempt': 2,
                         'retry_of': implementation['run_id']}
                third = dispatch_comment(retry)
                third['id'] = 102
                facts['issue_comments'].append(third)
                self.assertEqual('UPDATED', reconcile(api, 85, self.policy, NOW))
                state = parse_state(api.dashboard['body'], 85, self.policy)
                self.assertEqual('READY_FOR_HUMAN_MERGE', state['current_state'])
                self.assertEqual('PASS', state['merge_gate']['status'])
                self.assertEqual(retry['run_id'], state['active_run_id'])
                self.assertEqual('NO_OP', reconcile(api, 85, self.policy, NOW))

    def test_invalid_initial_retry_cannot_erase_failure(self):
        failed = dispatch_comment({**self.receipt, 'state': 'FAILED'})
        failed['id'] = 100
        for attempt, parent, target in ((1, None, HEAD), (2, 'missing-run', HEAD),
                                        (3, self.receipt['run_id'], HEAD),
                                        (2, self.receipt['run_id'], OLD)):
            with self.subTest(attempt=attempt, parent=parent, target=target):
                retry = {**self.receipt, 'run_id': 'synthetic-invalid-retry', 'attempt': attempt,
                         'retry_of': parent, 'target_sha': target}
                retry['dedup_key'] = dedup_key(85, retry)
                comment = dispatch_comment(retry)
                comment['id'] = 101
                api = Issue85API(self.policy, {**self.facts, 'issue_comments': [failed, comment]},
                                 render(initial_state(85, self.policy)))
                with self.assertRaises(ValueError):
                    reconcile(api, 85, self.policy, NOW)
                safe_stop(api, 85, self.policy)
                self.assertNotEqual('PASS', parse_state(api.dashboard['body'], 85, self.policy)['merge_gate']['status'])

    def test_malformed_armed_dispatch_status_preserves_corruption_and_warns(self):
        self.facts['pr'] = None
        for value in ([], {}, False, 1):
            with self.subTest(value=value):
                state = initial_state(85, self.policy)
                state['dispatch_state'] = value
                body = render(state)
                with self.assertRaises(ValueError):
                    parse_state(body, 85, self.policy)
                api = Issue85API(self.policy, self.facts, body)
                safe_stop(api, 85, self.policy)
                self.assertTrue(api.dashboard['body'].startswith(body))
                self.assertIn('langbench-dashboard-safe-stop', api.dashboard['body'])

    def test_old_head_wrong_identity_and_other_automation_review_not_trusted(self):
        self.facts['issue_comments'] = [dispatch_comment(self.receipt)]
        for mutation in ('head', 'author', 'automation', 'issue', 'pr'):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(self.report)
                user = None
                if mutation == 'head': report['head_sha'] = OLD
                elif mutation == 'author': user = {'login': 'other', 'id': 1, 'type': 'User'}
                elif mutation == 'automation': report['automation_id'] = 'preparation-automation'
                elif mutation == 'issue': report['issue'] = 86
                else: report['pr'] = 87
                self.facts['pr_comments'] = [record(WORK, report, user=user)]
                state = evaluate(85, self.policy, None, self.facts)
                self.assertNotEqual('PASS', state['merge_gate']['status'])
                self.assertNotEqual('PASS', state['work_review']['status'])
        self.facts['pr_comments'] = [record(WORK, self.report)]
        self.facts['ci_runs'][0]['head_sha'] = OLD
        self.assertNotEqual('PASS', evaluate(85, self.policy, None, self.facts)['merge_gate']['status'])

    def test_preparation_pr_does_not_bind_and_other_issue_state_rejected(self):
        self.facts['pr'].update(title='Issue #86: Register policy', body=f'Refs #86\nRelated Issue #85\nCurrent head: {HEAD}\n')
        self.assertFalse(references(self.facts['pr']['body'], 85))
        dashboard, facts = collect(Issue85API(self.policy, self.facts, None), 85, self.policy, None)
        self.assertIsNone(dashboard)
        self.assertIsNone(facts['pr'])
        self.assertEqual('AUTOMATION_ARMED', evaluate(85, self.policy, None, facts)['current_state'])
        with self.assertRaises(ValueError):
            parse_state(render(initial_state(85, self.policy)), 86, self.policy)


if __name__ == '__main__':
    unittest.main()
