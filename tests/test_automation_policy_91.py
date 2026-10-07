"""Issue 91 policy acceptance using synthetic GitHub facts, never live dispatch."""
import copy
import json
import subprocess
import unittest

from tools.automation_dashboard import (
    RECEIPT, WORK, dedup_key, evaluate, parse_state, render,
)
from tools.update_automation_dashboard import reconcile, references
from tests.test_automation_dashboard import FakeGitHub, HEAD, NOW, ROOT, fixtures, record


def fixture91():
    policy = json.loads((ROOT / '.github/automation-dashboard.json').read_text(encoding='utf-8'))['issues']['91']
    _, facts, report = fixtures()
    report.update(issue=91, pr=191, automation_id=policy['work_automation_id'])
    facts['pr'].update(number=191, title='Issue #91: Synthetic conflict fix',
                       body=f'Refs #91\nCurrent head: {HEAD}\n')
    facts['pr_comments'] = [record(WORK, report)]
    facts['ci_runs'][0]['pull_requests'] = [{'number': 191}]
    facts['dashboard_comment_id'] = None
    receipt = {'target_sha': HEAD, 'action_type': 'implementation_task',
               'purpose_id': policy['purpose'], 'state': 'SUCCEEDED',
               'run_id': 'synthetic-policy91-only', 'attempt': 1, 'retry_of': None}
    receipt['dedup_key'] = dedup_key(91, receipt)
    return policy, facts, report, receipt


def receipt_comment(receipt):
    return record(RECEIPT, {'schema_version': 1,
                           'repository': 'tetsujisugimori-coder/LangBench-Live',
                           'issue': 91, 'active': True, 'dispatch': receipt})


class Issue91API(FakeGitHub):
    def request(self, path, method='GET', data=None, raw=False):
        path = path.replace('/issues/91', '/issues/80').replace('/issues/191', '/issues/81')
        path = path.replace('/pulls/191', '/pulls/81')
        return super().request(path, method, data, raw)


class Policy91Registration(unittest.TestCase):
    def setUp(self):
        self.policy, self.facts, self.report, self.receipt = fixture91()

    def test_existing_policy_and_scope_preserved(self):
        config = json.loads((ROOT / '.github/automation-dashboard.json').read_text(encoding='utf-8'))
        before = json.loads(subprocess.check_output(
            ['git', 'show', 'df4c285035e8bac6ca2511b08e6acef65e8127d2:.github/automation-dashboard.json'],
            cwd=ROOT, text=True, encoding='utf-8'))
        self.assertEqual(set(before['issues']) | {'91'}, set(config['issues']))
        for issue, policy in before['issues'].items():
            self.assertEqual(policy, config['issues'][issue])
        self.assertEqual('preparation-comment-conflict-fix', self.policy['purpose'])
        self.assertEqual({'login': 'tetsujisugimori-coder', 'id': 265440097, 'type': 'User'}, self.policy['owner'])
        self.assertEqual(self.policy['owner'], self.policy['work_author'])
        self.assertEqual('6ac620a911e881918d0c5ae42bdf784d', self.policy['work_automation_id'])
        self.assertNotIn(self.policy['work_automation_id'], [p['work_automation_id'] for p in before['issues'].values()])
        self.assertIsNone(self.policy['initial_dispatch'])
        self.assertIsNone(self.policy['dashboard_comment_id'])
        self.assertEqual('.github/workflows/pull-local-main.yml', self.policy['dispatch_owners']['local_main_sync'])
        self.assertEqual({'windows_validation': 'NOT_REQUIRED', 'windows_measurement': 'NOT_REQUIRED',
                          'artifact_integrity': 'NOT_REQUIRED', 'measurement_result_pr': 'NOT_REQUIRED',
                          'live_smoke': 'REQUIRED'}, self.policy['requirements'])

    def test_unstarted_policy_roundtrip_never_grants_pass(self):
        self.facts['pr'] = None
        state = evaluate(91, self.policy, None, self.facts)
        self.assertEqual('AUTOMATION_ARMED', state['current_state'])
        self.assertEqual([], state['dispatches'])
        for key in ('active_action', 'purpose_id', 'dedup_key', 'dispatch_state', 'active_run_id'):
            self.assertIsNone(state[key])
        self.assertEqual('PENDING', state['merge_gate']['status'])
        self.assertEqual('PENDING', state['completion_gate']['status'])
        self.assertEqual(state, parse_state(render(state), 91, self.policy))

    def test_writer_updates_single_record_then_noop(self):
        self.facts['pr'] = None
        api = Issue91API(self.policy, self.facts, None)
        self.assertEqual('UPDATED', reconcile(api, 91, self.policy, NOW))
        first = copy.deepcopy(api.dashboard)
        self.assertEqual('NO_OP', reconcile(api, 91, self.policy, NOW))
        self.assertEqual(first, api.dashboard)
        self.assertEqual(1, len(api.writes))
        self.assertEqual('AUTOMATION_ARMED', parse_state(api.dashboard['body'], 91, self.policy)['current_state'])

    def test_successful_pr_without_receipt_cannot_bypass_start(self):
        state = evaluate(91, self.policy, None, self.facts)
        self.assertEqual('SAFE_STOPPED', state['current_state'])
        self.assertEqual('BLOCKED', state['merge_gate']['status'])
        self.assertIsNone(state['pr'])
        self.facts['issue_comments'] = [receipt_comment(self.receipt)]
        state = evaluate(91, self.policy, state, self.facts)
        self.assertEqual('READY_FOR_HUMAN_MERGE', state['current_state'])
        self.assertEqual('PASS', state['merge_gate']['status'])
        self.assertEqual('PENDING', state['completion_gate']['status'])

    def test_wrong_scope_author_and_automation_evidence_rejected(self):
        for mutation in ('issue', 'purpose', 'author', 'automation'):
            with self.subTest(mutation=mutation):
                facts = copy.deepcopy(self.facts)
                comment = receipt_comment(self.receipt)
                if mutation == 'author':
                    comment['user'] = {'login': 'other', 'id': 1, 'type': 'User'}
                elif mutation in ('issue', 'purpose'):
                    value = json.loads(comment['body'].split('\n')[1])
                    if mutation == 'issue':
                        value['issue'] = 88
                    else:
                        value['dispatch']['purpose_id'] = 'automation-startup-preparation'
                    comment = record(RECEIPT, value)
                else:
                    report = {**self.report, 'automation_id': '6ac5a9e2b1708191b122d3d91687b94d'}
                    facts['pr_comments'] = [record(WORK, report)]
                facts['issue_comments'] = [comment]
                if mutation == 'purpose':
                    with self.assertRaisesRegex(ValueError, 'Invalid authenticated dispatch receipt'):
                        evaluate(91, self.policy, None, facts)
                else:
                    self.assertNotEqual('PASS', evaluate(91, self.policy, None, facts)['merge_gate']['status'])

    def test_preparation_pr_binds_only_its_issue(self):
        body = ('Refs #92\n\nRelated fix: '
                'https://github.com/tetsujisugimori-coder/LangBench-Live/issues/91\n')
        self.assertTrue(references(body, 92))
        self.assertFalse(references(body, 91))


if __name__ == '__main__':
    unittest.main()
