import unittest

from tools.verify_measurement_validation_gate import SYNC_WORKFLOW, verify


SHA = "a" * 40
REPO = "tetsujisugimori-coder/LangBench-Live"


def fixtures():
    # Shape of hydrated pulls/{number}, not the smaller commits/{sha}/pulls item.
    pulls = [{"number": 72, "merged_at": "now", "merge_commit_sha": SHA, "target_compare_status": "identical",
              "base": {"ref": "main", "repo": {"full_name": REPO}},
              "merged_by": {"type": "User"}}]
    runs = {"workflow_runs": [{"id": 123, "path": SYNC_WORKFLOW, "event": "push",
             "head_branch": "main", "head_sha": SHA, "head_repository": {"full_name": REPO},
             "status": "completed", "conclusion": "success"}]}
    jobs = {"123": {"jobs": [{"name": "verify-merge", "status": "completed", "conclusion": "success"},
                              {"name": "pull-main", "status": "completed", "conclusion": "success"}]}}
    return pulls, runs, jobs


class MeasurementValidationGateTests(unittest.TestCase):
    def test_unhydrated_commit_pull_response_is_rejected(self):
        pulls, runs, jobs = fixtures(); pulls[0].pop("merged_by")
        with self.assertRaisesRegex(ValueError, "human-merged"):
            verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA, pulls, runs, jobs)

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

    def test_all_sync_and_compare_dimensions_fail_closed(self):
        mutations = [
            lambda p, r, j: p[0].update(target_compare_status="behind"),
            lambda p, r, j: p[0].update(target_compare_status="diverged"),
            lambda p, r, j: p[0].update(target_compare_status="unknown"),
            lambda p, r, j: r["workflow_runs"][0].update(path="other.yml"),
            lambda p, r, j: r["workflow_runs"][0].update(event="pull_request"),
            lambda p, r, j: r["workflow_runs"][0].update(head_branch="topic"),
            lambda p, r, j: r["workflow_runs"][0].update(head_sha="b" * 40),
            lambda p, r, j: r["workflow_runs"][0].update(status="in_progress"),
            lambda p, r, j: r["workflow_runs"][0].update(conclusion="failure"),
            lambda p, r, j: j["123"]["jobs"].pop(),
        ]
        for mutate in mutations:
            pulls, runs, jobs = fixtures(); mutate(pulls, runs, jobs)
            with self.assertRaises(ValueError):
                verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA, pulls, runs, jobs)

    def test_human_merge_ancestor_ahead_is_accepted(self):
        pulls, runs, jobs = fixtures(); pulls[0].update(merge_commit_sha="c" * 40, target_compare_status="ahead")
        self.assertEqual(123, verify(REPO, "refs/heads/main", "workflow_dispatch", SHA, SHA, SHA,
                                     pulls, runs, jobs)["sync_run_id"])


if __name__ == "__main__": unittest.main()
