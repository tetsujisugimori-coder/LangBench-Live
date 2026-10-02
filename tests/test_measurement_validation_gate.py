import unittest

from tools.verify_measurement_validation_gate import SYNC_WORKFLOW, verify


SHA = "a" * 40
REPO = "tetsujisugimori-coder/LangBench-Live"


def fixtures():
    pulls = [{"number": 72, "merged_at": "now", "merge_commit_sha": SHA,
              "base": {"ref": "main", "repo": {"full_name": REPO}},
              "merged_by": {"type": "User"}}]
    runs = {"workflow_runs": [{"id": 123, "path": SYNC_WORKFLOW, "event": "push",
             "head_branch": "main", "head_sha": SHA, "head_repository": {"full_name": REPO},
             "status": "completed", "conclusion": "success"}]}
    jobs = {"123": {"jobs": [{"name": "verify-merge", "status": "completed", "conclusion": "success"},
                              {"name": "pull-main", "status": "completed", "conclusion": "success"}]}}
    return pulls, runs, jobs


class MeasurementValidationGateTests(unittest.TestCase):
    def test_accepts_exact_main_and_official_successful_sync(self):
        pulls, runs, jobs = fixtures()
        self.assertEqual(123, verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA,
                                     pulls, runs, jobs)["sync_run_id"])

    def test_rejects_branch_sha_main_change_and_foreign_sync(self):
        for field in ("ref", "main_after"):
            pulls, runs, jobs = fixtures()
            args = dict(repository=REPO, ref="refs/heads/main", event="workflow_dispatch", run_sha=SHA,
                        main_before=SHA, main_after=SHA, pulls=pulls, runs=runs, jobs=jobs)
            args[field] = "refs/heads/topic" if field == "ref" else "b" * 40
            with self.assertRaises(ValueError): verify(**args)
        pulls, runs, jobs = fixtures(); runs["workflow_runs"][0]["head_repository"]["full_name"] = "other/repo"
        with self.assertRaises(ValueError): verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA,
                                                   pulls, runs, jobs)

    def test_rejects_failed_or_incomplete_sync_jobs_and_bot_merge(self):
        pulls, runs, jobs = fixtures(); jobs["123"]["jobs"][1]["conclusion"] = "failure"
        with self.assertRaises(ValueError): verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA,
                                                   pulls, runs, jobs)
        pulls, runs, jobs = fixtures(); pulls[0]["merged_by"]["type"] = "Bot"
        with self.assertRaises(ValueError): verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA,
                                                   pulls, runs, jobs)


if __name__ == "__main__": unittest.main()
