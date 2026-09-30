import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_function_call_analysis_gate import verify


class AnalysisGateTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.pull = {"number": 69, "state": "closed", "merged": True,
                     "merged_at": "2026-10-01T00:00:00Z", "body": "Issue #68 / PR-A 段階",
                     "merge_commit_sha": self.sha, "head": {"repo": {"full_name": "owner/repo"}},
                     "base": {"ref": "main", "repo": {"full_name": "owner/repo"}}}
        self.run = {"id": 123, "repository": {"full_name": "owner/repo"},
                    "head_repository": {"full_name": "owner/repo"},
                    "path": ".github/workflows/pull-local-main.yml",
                    "name": "Pull local main after verified merge", "event": "push",
                    "head_branch": "main", "head_sha": self.sha, "status": "completed", "conclusion": "success"}

    def check(self, pull=None, run=None, ref="refs/heads/main", sha=None, sync_sha=None, run_id=123):
        return verify("owner/repo", ref, sha or self.sha, sync_sha or self.sha,
                      run_id, pull or self.pull, run or self.run)

    def test_accepts_only_issue_68_pr_a_with_matching_main_sync(self):
        self.assertEqual([], self.check())

    def test_rejects_dispatch_from_branch_or_tag(self):
        self.assertIn("workflow ref is not protected main", self.check(ref="refs/heads/topic"))
        self.assertIn("workflow ref is not protected main", self.check(ref="refs/tags/v1"))

    def test_rejects_unrelated_or_malformed_pull_requests(self):
        mutations = [
            lambda p: p.update(body="Issue #70 / PR-A"), lambda p: p.update(body="Issue #68 only"),
            lambda p: p.update(number=70), lambda p: p.update(state="open"),
            lambda p: p.update(merged_at=None),
            lambda p: p.update(merged=False), lambda p: p["base"].update(ref="release"),
            lambda p: p["base"]["repo"].update(full_name="other/repo"),
            lambda p: p["head"]["repo"].update(full_name="other/repo"),
            lambda p: p.update(merge_commit_sha="b" * 40),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                pull = copy.deepcopy(self.pull); mutate(pull)
                self.assertTrue(self.check(pull=pull))

    def test_rejects_wrong_sync_run(self):
        for key, value in [("id", 456), ("path", "other.yml"), ("name", "other"),
                           ("repository", {"full_name": "other/repo"}),
                           ("head_repository", {"full_name": "other/repo"}),
                           ("event", "workflow_dispatch"), ("head_branch", "topic"),
                           ("head_sha", "b" * 40), ("status", "in_progress"), ("conclusion", "failure")]:
            with self.subTest(key=key):
                run = copy.deepcopy(self.run); run[key] = value
                self.assertTrue(self.check(run=run))
        self.assertTrue(self.check(sync_sha="b" * 40))
        self.assertTrue(self.check(run_id=456))


if __name__ == "__main__": unittest.main()
