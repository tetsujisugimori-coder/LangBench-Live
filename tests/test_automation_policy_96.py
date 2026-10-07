"""I-01 policy safety before implementation; synthetic facts, no dispatch."""
import json
import subprocess
import unittest

from tools.automation_dashboard import evaluate, parse_state, render
from tests.test_automation_dashboard import ROOT, fixtures


class Policy96Registration(unittest.TestCase):
    def test_existing_policies_preserved_and_no_initial_execution(self):
        config = json.loads((ROOT / '.github/automation-dashboard.json').read_text(encoding='utf-8'))
        before = json.loads(subprocess.check_output(
            ['git', 'show', '36362bc61f964bb006b1cae4cefec58a1d140168:.github/automation-dashboard.json'],
            cwd=ROOT, text=True, encoding='utf-8'))
        self.assertEqual(before['repository'], config['repository'])
        self.assertEqual(before['schema_version'], config['schema_version'])
        self.assertTrue(set(before['issues']) | {'96'} <= set(config['issues']))
        for issue, policy in before['issues'].items():
            self.assertEqual(policy, config['issues'][issue])
        policy = config['issues']['96']
        self.assertEqual('work-owner-resume-i01', policy['purpose'])
        self.assertIsNone(policy['initial_dispatch'])
        self.assertIsNone(policy['dashboard_comment_id'])
        self.assertEqual('REQUIRED', policy['requirements']['live_smoke'])
        self.assertEqual('.github/workflows/pull-local-main.yml', policy['dispatch_owners']['local_main_sync'])

    def test_no_receipt_means_no_start_or_pass(self):
        policy = json.loads((ROOT / '.github/automation-dashboard.json').read_text(encoding='utf-8'))['issues']['96']
        _, facts, _ = fixtures()
        facts['pr'] = None
        facts['issue_comments'] = []
        state = evaluate(96, policy, None, facts)
        self.assertEqual('AUTOMATION_ARMED', state['current_state'])
        self.assertEqual([], state['dispatches'])
        self.assertIsNone(state['active_run_id'])
        self.assertEqual('PENDING', state['merge_gate']['status'])
        self.assertEqual('PENDING', state['completion_gate']['status'])
        self.assertEqual(state, parse_state(render(state), 96, policy))
        self.assertEqual(state, evaluate(96, policy, state, facts))


if __name__ == '__main__':
    unittest.main()
