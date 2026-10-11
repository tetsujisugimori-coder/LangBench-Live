"""Synthetic registration candidates, not live Work event proofs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools import startup_preparation as p
from tests.test_startup_preparation import input_fixture


class ReviewRegistrationRequestTests(unittest.TestCase):
    def setUp(self):
        self.v = input_fixture()
        self.v.update(issue=112, purpose='startup-review-registration-i07', work_automation_id=None)
        self.s = p.new_state(self.v)

    def test_target_not_invented(self):
        r = p.review_registration_request(self.v, self.s)
        self.assertEqual(r['next_action'], 'WAIT_FOR_TARGET')
        for key in ('pr', 'head_sha', 'task_id', 'create_args'):
            self.assertIsNone(r[key])

    def test_real_target_candidate_and_head_change(self):
        r = p.review_registration_request(self.v, self.s, 113, 'a'*40)
        args = r['create_args']
        self.assertEqual(args['triggers'][0]['params']['pull_request_number'], 113)
        self.assertEqual(args['triggers'][0]['params']['repository'], self.v['repository'])
        self.assertIn('Issue #112', args['prompt'])
        self.assertIn('a'*40, args['prompt'])
        self.assertIn('GitHub書込みゼロ', args['prompt'])
        self.assertIn('is_enabled=false', args['prompt'])
        self.assertFalse(r['registration_performed'])
        self.assertFalse(r['target_verified'])
        new = p.review_registration_request(self.v, self.s, 113, 'b'*40)
        self.assertNotIn('a'*40, new['create_args']['prompt'])
        self.assertNotEqual(r, new)
        self.assertEqual(self.s, p.new_state(self.v))

    def test_existing_id_or_unknown_requires_reconciliation(self):
        unknown = p.mark_unknown(self.s, 'review')
        r = p.review_registration_request(self.v, unknown, 113, 'a'*40)
        self.assertEqual(r['next_action'], 'RECONCILE_ONLY')
        self.assertIsNone(r['create_args'])
        self.v['work_automation_id'] = 'a'*32
        self.v['input_version'] += 1
        s = p.rebase(self.s, self.v)
        r = p.review_registration_request(self.v, s, 113, 'a'*40)
        self.assertEqual(r['task_id'], 'a'*32)
        self.assertIsNone(r['create_args'])

    def test_scope_version_and_partial_target_rejected(self):
        for pr, head in ((None, 'a'*40), (113, None), (0, 'a'*40), (True, 'a'*40), (113, 'a'*39)):
            with self.subTest(pr=pr, head=head), self.assertRaises(ValueError):
                p.review_registration_request(self.v, self.s, pr, head)
        other = copy.deepcopy(self.v); other['input_version'] += 1
        with self.assertRaises(ValueError): p.review_registration_request(other, self.s, 113, 'a'*40)

    def test_v2_binding_and_approved_prompt_preserved(self):
        from tests.test_preparation_evidence import fixture
        v, _, _ = fixture('PR_BOUND')
        v['work_automation_id'] = None
        v['registration_prompts']['review']['events'].append('synchronize')
        state = p.new_state(v)
        r = p.review_registration_request(v, state)
        self.assertEqual(r['create_args']['prompt'], v['registration_prompts']['review']['text'])
        with self.assertRaises(ValueError): p.review_registration_request(v, state, v['pr']+1, v['head_sha'])
        v['registration_prompts']['review']['events'].remove('synchronize')
        r = p.review_registration_request(v, p.new_state(v))
        self.assertEqual(r['next_action'], 'ACQUIRE_APPROVED_PROMPT')
        self.assertIsNone(r['create_args'])
        other = copy.deepcopy(self.v); other['repository'] = 'wrong/repository'
        with self.assertRaises(ValueError): p.review_registration_request(other, self.s, 113, 'a'*40)

    def test_cli_opt_in_and_legacy_output_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp); inp = d/'input.json'
            inp.write_text(p.canonical(self.v), encoding='utf-8')
            cmd = [sys.executable, '-B', 'tools/startup_preparation.py', '--input', str(inp),
                   '--state', str(d/'state.json'), '--output', str(d/'out')]
            before = subprocess.run(cmd, cwd=root, capture_output=True)
            self.assertEqual(before.returncode, 0, before.stderr)
            # Existing rebase normalizes the first unobserved cache to WAITING.
            subprocess.run(cmd, cwd=root, check=True, capture_output=True)
            old = {f.name:f.read_bytes() for f in (d/'out').iterdir()}
            result = subprocess.run(cmd+['--review-registration-request', '--review-pr', '113',
                                         '--review-head', 'a'*40], cwd=root, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name, data in old.items():
                actual = (d/'out'/name).read_bytes()
                if name == 'summary.md':
                    # Existing input-field sets can change line order across processes.
                    self.assertEqual(sorted(actual.splitlines()), sorted(data.splitlines()))
                else:
                    self.assertEqual(actual, data)
            r = json.loads((d/'out/review_registration_request.json').read_text(encoding='utf-8'))
            self.assertEqual(r['next_action'], 'CREATE_CANDIDATE')
            invalid = subprocess.run(cmd+['--review-pr', '113'], cwd=root, capture_output=True)
            self.assertNotEqual(invalid.returncode, 0)
