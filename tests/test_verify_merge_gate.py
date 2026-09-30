import unittest

from tools.verify_merge_gate import verify

REPOSITORY = "tetsujisugimori-coder/LangBench-Live"
TARGET = "a" * 40
HEAD = "b" * 40


def pull(**changes):
    value = {"number": 67, "merged_at": "2026-09-30T00:00:00Z", "merge_commit_sha": TARGET,
             "base": {"ref": "main", "repo": {"full_name": REPOSITORY}}, "head": {"sha": HEAD}}
    value.update(changes)
    return value


class VerifyMergeGateTest(unittest.TestCase):
    def checked(self, pulls, status="identical", target=TARGET):
        return verify(REPOSITORY, "refs/heads/main", target, pulls, status)

    def test_supported_merge_results(self):
        for mode, merge_sha, status in (("normal", TARGET, "identical"),
                                        ("squash", TARGET, "identical"),
                                        ("rebase", "c" * 40, "ahead")):
            with self.subTest(mode=mode):
                self.assertEqual(67, self.checked([pull(merge_commit_sha=merge_sha)], status)["pr_number"])

    def test_non_pr_and_unsafe_pr_events_stop(self):
        cases = {
            "direct-push": [],
            "closed-only": [pull(merged_at=None)],
            "other-base": [pull(base={"ref": "release", "repo": {"full_name": REPOSITORY}})],
            "other-repository": [pull(base={"ref": "main", "repo": {"full_name": "other/repo"}})],
            "ambiguous": [pull(), pull(number=68, head={"sha": "d" * 40})],
        }
        for name, pulls in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError): self.checked(pulls)

    def test_api_failure_unknown_sha_and_unsupported_comparison_stop(self):
        with self.assertRaises(ValueError): self.checked({"message": "API failure"})
        with self.assertRaises(ValueError): self.checked([pull()], target="unknown")
        for status in ("behind", "diverged", "404", "error"):
            with self.subTest(status=status), self.assertRaises(ValueError): self.checked([pull()], status)


if __name__ == "__main__": unittest.main()
