"""V4 advisory read-only observations never manufacture Gate evidence.

All facts are synthetic. No production API calls or Work service assumptions.
"""
import json
from pathlib import Path
import unittest

from tools.automation_dashboard import (REPOSITORY, evaluate, observed_pr_facts, render)


ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
MERGE = "b" * 40


class V4ObservedFactsTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / ".github/automation-dashboard.json").read_text(
            encoding="utf-8"))["issues"]["85"]
        self.pr = {"number": 120, "head": {"sha": HEAD},
                   "base": {"repo": {"full_name": REPOSITORY}, "ref": "main"},
                   "body": "Refs #85\nCurrent head: " + HEAD + "\n",
                   "merged": False, "state": "open"}

    def facts(self):
        return {"issue_comments": [], "pr": self.pr,
                "pr_comments": [], "reviews": []}

    def test_receipt_missing_does_not_erase_observed_pr(self):
        facts = self.facts()
        state = evaluate(85, self.policy, None, facts)
        self.assertEqual(state["current_state"], "SAFE_STOPPED")
        self.assertEqual(state["merge_gate"]["status"], "BLOCKED")
        self.assertIsNone(state["pr"])
        observed = observed_pr_facts(85, self.policy, facts)
        self.assertEqual(observed["status"], "OBSERVED")
        self.assertEqual(observed["head_sha"], HEAD)
        self.assertEqual(observed["read_only"], "INSPECT_BOUNDED_FACTS")
        self.assertEqual(observed["effectful"], "EXISTING_GATES_ONLY")
        rendered = render(state, observed)
        self.assertIn("GitHubで観測した事実", rendered)
        self.assertIn(HEAD, rendered)
        self.assertIn("初期dispatch", rendered)
        self.assertIn('"merge_gate"', rendered)
        self.assertIn('"status":"BLOCKED"', rendered)

    def test_other_repository_or_issue_does_not_observe(self):
        facts = self.facts()
        facts["pr"]["base"]["repo"]["full_name"] = "another/repository"
        self.assertEqual(observed_pr_facts(85, self.policy, facts)["status"], "SCOPE_UNVERIFIED")
        facts["pr"]["base"]["repo"]["full_name"] = REPOSITORY
        facts["pr"]["body"] = "Refs #102\n"
        self.assertEqual(observed_pr_facts(85, self.policy, facts)["status"], "SCOPE_UNVERIFIED")

    def test_bad_merge_identity_is_not_human_merge(self):
        facts = self.facts()
        facts["pr"].update(merged=True, merge_commit_sha=MERGE, merged_at="2026-10-10T00:00:00Z")
        self.assertEqual(observed_pr_facts(85, self.policy, facts)["status"], "SCOPE_UNVERIFIED")
        facts["pr"]["merged_by"] = {"type": "User"}
        observed = observed_pr_facts(85, self.policy, facts)
        self.assertTrue(observed["merged"])
        self.assertEqual(observed["merge_sha"], MERGE)
        self.assertEqual(observed["local_sync"]["status"], "PENDING")

    def test_unknown_facts_never_mean_success(self):
        missing = observed_pr_facts(85, self.policy, {"pr": None})
        self.assertEqual(missing["status"], "NOT_OBSERVED")
        self.assertEqual(missing["read_only"], "INSPECT_SCOPE")
        self.assertNotIn("pr", missing)
        observed = observed_pr_facts(85, self.policy, self.facts())
        self.assertEqual(observed["ci_ubuntu"]["status"], "PENDING")
        self.assertEqual(observed["work_review"]["status"], "PENDING")
        self.assertEqual(observed["local_sync"]["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
