"""The 24 Issue #80 acceptance fixtures, plus API/trust integration regressions.

All runs/SHAs here are synthetic. No benchmark or self-hosted execution.
"""
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

from tools.automation_dashboard import (BOT, REPOSITORY, START, WORK, RECEIPT, SMOKE, author_matches,
                                        evaluate, initial_state, parse_state, render, result)
from tools.update_automation_dashboard import (GitHub, SafeRedirect, collect, reconcile, safe_stop, main)

ROOT = Path(__file__).resolve().parents[1]
HEAD, OLD, MERGE = "a" * 40, "b" * 40, "c" * 40
NOW = "2026-10-04T12:00:00+00:00"


def record(marker, value, ident=100, user=None):
    return {"id": ident, "user": user or {"login": "tetsujisugimori-coder", "id": 265440097, "type": "User"},
            "body": "<!-- " + marker + "\n" + json.dumps(value) + "\n-->"}


def run(ident, filename, workflow_id, head=HEAD, event="pull_request", names=None):
    value = {"id": ident, "workflow_id": workflow_id, "path": ".github/workflows/" + filename,
             "repository": {"full_name": REPOSITORY}, "head_repository": {"full_name": REPOSITORY},
             "head_sha": head, "event": event, "head_branch": "main" if event == "push" else "feature",
             "status": "completed", "conclusion": "success", "run_attempt": 1,
             "pull_requests": [{"number": 81}]}
    jobs = [{"name": name, "status": "completed", "conclusion": "success", "head_sha": head,
             "steps": [{"name": "Run python -B -m unittest discover -s tests -q", "conclusion": "success"}]}
            for name in (names or ["python-tests (ubuntu-latest)", "python-tests (windows-latest)"])]
    return value, jobs


def fixtures():
    policy = json.loads((ROOT / ".github/automation-dashboard.json").read_text(encoding="utf-8"))["issues"]["80"]
    report = {"schema_version": 1, "kind": "work_review", "repository": REPOSITORY, "issue": 80, "pr": 81,
              "head_sha": HEAD, "automation_id": policy["work_automation_id"], "verdict": "PASS",
              "blockers": [], "active_blocker": None, "follow_up": [], "follow_up_recorded": True, "conditions": {}}
    ci, jobs = run(10, "python-tests.yml", 1)
    facts = {"pr": {"number": 81, "head": {"sha": HEAD}, "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
                    "title": "Issue #80: Dashboard", "body": f"Refs #80\nCurrent head: {HEAD}\n", "state": "open", "draft": False,
                    "merged": False, "merge_commit_sha": None, "updated_at": NOW},
             "issue_comments": [], "pr_comments": [record(WORK, report)], "reviews": [],
             "workflow_ids": {"python-tests.yml": 1, "pull-local-main.yml": 2,
                              "measurement-validation-windows.yml": 3, "function-call-analysis-windows.yml": 4},
             "ci_runs": [ci], "sync_runs": [], "jobs": {"10": jobs}, "sync_reports": {},
             "dashboard_comment_id": policy["dashboard_comment_id"], "condition_runs": {}, "condition_artifacts": {}, "result_pr": None}
    return policy, facts, report


class FakeGitHub(GitHub):
    """Strict in-memory REST service: exercises actual adapter read/write paths."""
    def __init__(self, policy, facts, body="## LangBench-Live Automation Dashboard\nlegacy state: PASS"):
        super().__init__("test-token")
        self.policy, self.facts = policy, facts
        self.dashboard = {"id": policy.get("dashboard_comment_id") or 5979234464,
                          "user": policy["owner"], "body": body} if body is not None else None
        self.writes = []
        self.hook = None

    def request(self, path, method="GET", data=None, raw=False):
        if self.hook:
            self.hook(path, method)
        suffix = path.removeprefix(self.root)
        if method != "GET":
            self.writes.append((method, suffix, copy.deepcopy(data)))
            if method == "POST":
                if self.dashboard:
                    raise AssertionError("Duplicate Dashboard creation")
                self.dashboard = {"id": 5979234464, "user": BOT, "body": data["body"]}
            elif method == "PATCH" and self.dashboard and suffix == f'/issues/comments/{self.dashboard["id"]}':
                self.dashboard["body"] = data["body"]
            else:
                raise AssertionError((method, suffix))
            return copy.deepcopy(self.dashboard)
        clean = suffix.split("?")[0]
        if "page=2" in suffix:
            raise AssertionError("Unexpected second fixture page")
        routes = {
            "/issues/80": {"number": 80, "state": "open"},
            "/issues/80/comments": self.facts["issue_comments"] + ([self.dashboard] if self.dashboard else []),
            "/issues/81/comments": self.facts["pr_comments"], "/pulls/81/reviews": self.facts["reviews"],
            "/pulls/81": self.facts["pr"], "/pulls": [self.facts["pr"]] if self.facts["pr"] else [],
            "/actions/workflows": {"workflows": [{"id": ident, "path": ".github/workflows/" + name, "state": "active"}
                                                 for name, ident in self.facts["workflow_ids"].items()]},
            "/actions/workflows/python-tests.yml/runs": {"workflow_runs": self.facts["ci_runs"]},
            "/actions/workflows/pull-local-main.yml/runs": {"workflow_runs": self.facts["sync_runs"]},
        }
        for value in self.facts["ci_runs"] + self.facts["sync_runs"]:
            routes[f'/actions/runs/{value["id"]}/attempts/{value["run_attempt"]}/jobs'] = {"jobs": self.facts["jobs"].get(str(value["id"]), [])}
        for ident, value in self.facts["condition_runs"].items():
            routes[f"/actions/runs/{ident}"] = value
        for ident, value in self.facts["condition_artifacts"].items():
            routes[f"/actions/artifacts/{ident}"] = value
        if clean not in routes:
            raise AssertionError(f"Unexpected API route {clean}")
        return copy.deepcopy(routes[clean])

    def sync_report(self, value):
        return copy.deepcopy(self.facts["sync_reports"].get(str(value["id"])))


class DashboardAcceptanceFixtures(unittest.TestCase):
    def setUp(self):
        self.policy, self.facts, self.report = fixtures()

    def state(self, previous=None):
        self.facts["pr_comments"] = [record(WORK, self.report)]
        return evaluate(80, self.policy, previous, self.facts)

    def gate(self, expected):
        state = self.state()
        self.assertEqual(expected, state["merge_gate"]["status"], state["merge_gate"])
        return state

    def merged(self):
        self.facts["pr"].update(merged=True, state="closed", merge_commit_sha=MERGE,
                                merged_at=NOW, merged_by=self.policy["owner"])

    def synchronized(self, target=MERGE):
        value, jobs = run(20, "pull-local-main.yml", 2, target, "push", ["verify-merge", "pull-main"])
        self.facts["sync_runs"] = [value]
        self.facts["jobs"]["20"] = jobs
        self.facts["sync_reports"]["20"] = {
            "schema_version": 1, "repository": REPOSITORY, "pr": 81, "pr_head_sha": HEAD,
            "merge_sha": MERGE, "target_sha": target, "before_sha": OLD, "after_sha": target,
            "run_id": "20", "run_attempt": 1, "status": "success", "protected_preserved": True, "protected_files": 9}

    def test_01_new_dashboard(self):
        self.policy["dashboard_comment_id"] = None
        api = FakeGitHub(self.policy, self.facts, None)
        self.assertEqual("UPDATED", reconcile(api, 80, self.policy, NOW))
        self.assertEqual(["POST"], [w[0] for w in api.writes])
        self.assertEqual(81, parse_state(api.dashboard["body"], 80, self.policy)["pr"])

    def test_02_same_comment_update_and_legacy_migration(self):
        api = FakeGitHub(self.policy, self.facts)
        reconcile(api, 80, self.policy, NOW)
        self.assertEqual(5979234464, api.dashboard["id"])
        self.assertEqual(["PATCH"], [w[0] for w in api.writes])
        self.assertEqual(self.policy["initial_dispatch"], parse_state(api.dashboard["body"], 80, self.policy)["dispatches"][0])

    def test_03_event_reprocessing(self):
        api = FakeGitHub(self.policy, self.facts)
        reconcile(api, 80, self.policy, NOW)
        body = api.dashboard["body"]
        self.assertEqual("NO_OP", reconcile(api, 80, self.policy, "later"))
        self.assertEqual(body, api.dashboard["body"])
        self.assertEqual(1, len(api.writes))

    def test_04_out_of_order_event_uses_latest_facts(self):
        state = self.gate("PASS")
        self.facts["pr"]["head"]["sha"] = OLD
        new = self.state(state)
        self.assertEqual(OLD, new["head_sha"])
        # A delayed old event contains no authority in the reconcile API.
        again = self.state(new)
        self.assertEqual(new, again)
        self.assertNotEqual("READY_FOR_HUMAN_MERGE", again["current_state"])

    def test_05_stale_work(self):
        self.report["head_sha"] = OLD
        self.gate("STALE")

    def test_06_stale_ci(self):
        self.facts["ci_runs"][0]["head_sha"] = OLD
        self.gate("STALE")

    def test_07_current_work_pass(self):
        self.assertEqual("READY_FOR_HUMAN_MERGE", self.gate("PASS")["current_state"])

    def test_08_partial_ci(self):
        self.facts["jobs"]["10"][1].update(status="in_progress", conclusion=None)
        self.gate("PENDING")

    def test_09_ci_failure(self):
        self.facts["ci_runs"][0]["conclusion"] = "failure"
        self.gate("BLOCKED")

    def test_10_measurement_not_required(self):
        self.assertEqual("NOT_REQUIRED", self.gate("PASS")["conditions"]["windows_measurement"]["status"])

    def test_11_required_measurement_pending(self):
        self.policy["requirements"]["windows_measurement"] = "REQUIRED"
        self.gate("PENDING")

    def test_12_required_measurement_success(self):
        self.policy["requirements"]["windows_measurement"] = "REQUIRED"
        value, _ = run(30, "function-call-analysis-windows.yml", 4, HEAD, "workflow_dispatch")
        value["head_branch"] = "main"
        self.facts["condition_runs"]["30"] = value
        self.report["conditions"]["windows_measurement"] = {"status": "PASS", "head_sha": HEAD, "run_id": 30}
        self.gate("PASS")
        value["path"] = ".github/workflows/arbitrary.yml"
        self.gate("ERROR")

    def test_13_artifact_integrity_failure(self):
        self.policy["requirements"]["artifact_integrity"] = "REQUIRED"
        self.report["conditions"]["artifact_integrity"] = {"status": "BLOCKED", "head_sha": HEAD}
        self.gate("BLOCKED")

    def test_14_arbitrary_comment_spoof_rejected(self):
        attacker = {"login": "attacker", "id": 9, "type": "User"}
        self.facts["pr_comments"] = [record(WORK, self.report, user=attacker),
                                     {"id": 101, "user": self.policy["owner"], "body": f"WORK_REVIEW_PASS head={HEAD}"}]
        state = evaluate(80, self.policy, None, self.facts)
        self.assertEqual("PENDING", state["work_review"]["status"])
        self.assertNotEqual("PASS", state["merge_gate"]["status"])
        self.report["automation_id"] = "unregistered"
        self.gate("PENDING")

    def test_15_head_change_invalidates_gate(self):
        previous = self.gate("PASS")
        self.facts["pr"]["head"]["sha"] = OLD
        state = self.state(previous)
        self.assertEqual("STALE", state["work_review"]["status"])
        self.assertNotEqual("PASS", state["merge_gate"]["status"])

    def test_16_merge_without_sync_not_completed(self):
        self.merged()
        self.assertEqual("MERGED_SYNC_PENDING", self.state()["current_state"])

    def test_17_exact_sync_and_completion_smoke(self):
        self.merged(); self.synchronized()
        self.assertEqual("LOCAL_SYNCED", self.state()["current_state"])
        self.assertEqual("PENDING", self.state()["completion_gate"]["status"])
        self.facts["issue_comments"] = [record(SMOKE, {"schema_version": 1, "repository": REPOSITORY, "issue": 80,
            "pr": 81, "merge_sha": MERGE, "dashboard_comment_id": 5979234464,
            "sync_run_id": 20, "observed_state": "LOCAL_SYNCED", "status": "PASS"})]
        self.assertEqual("COMPLETED", self.state()["current_state"])
        self.facts["sync_reports"]["20"]["protected_preserved"] = False
        self.assertEqual("ERROR", self.state()["local_sync"]["status"])

    def test_18_other_sha_sync_not_reused(self):
        self.merged(); self.synchronized(OLD)
        self.assertEqual("MERGED_SYNC_PENDING", self.state()["current_state"])

    def test_19_duplicate_event(self):
        state = self.state()
        self.facts["pr_comments"] *= 2
        self.assertEqual(state, evaluate(80, self.policy, state, self.facts))

    def test_20_retry_new_attempt_is_authoritative(self):
        value = self.facts["ci_runs"][0]
        value.update(run_attempt=2, status="in_progress", conclusion=None)
        self.gate("PENDING")
        value.update(status="completed", conclusion="success")
        self.gate("PASS")

    def test_21_concurrent_head_update_fail_closed(self):
        api = FakeGitHub(self.policy, self.facts)
        def hook(path, method):
            if method == "PATCH":
                api.facts["pr"]["head"]["sha"] = OLD
                api.hook = None
        api.hook = hook
        self.assertEqual("RACE_BLOCKED", reconcile(api, 80, self.policy, NOW))
        state = parse_state(api.dashboard["body"], 80, self.policy)
        self.assertEqual("SAFE_STOPPED", state["current_state"])
        self.assertEqual("STALE", state["merge_gate"]["status"])

    def test_22_dashboard_api_disagreement_fail_closed(self):
        previous = self.gate("PASS")
        previous["head_sha"] = OLD
        self.facts["pr_comments"] = []
        state = evaluate(80, self.policy, previous, self.facts)
        self.assertEqual(HEAD, state["head_sha"])
        self.assertNotEqual("PASS", state["merge_gate"]["status"])
        previous["pr"] = 999
        with self.assertRaisesRegex(ValueError, "conflict"):
            evaluate(80, self.policy, previous, self.facts)

    def test_23_ownership_dedup_preserved_and_duplicates_block(self):
        previous = initial_state(80, self.policy)
        receipt = copy.deepcopy(self.policy["initial_dispatch"])
        receipt["run_id"] = "second-task"
        self.facts["issue_comments"] = [record(RECEIPT, {"schema_version": 1, "repository": REPOSITORY, "issue": 80, "dispatch": receipt})]
        state = self.state(previous)
        self.assertEqual(previous["dispatch_owners"], state["dispatch_owners"])
        self.assertEqual(previous["dedup_key"], state["dedup_key"])
        self.assertEqual(2, len(state["dispatches"]))
        self.assertEqual("BLOCKED", state["merge_gate"]["status"])
        self.assertIn("DUPLICATE_DISPATCH_DETECTED", state["blockers"][0])

    def test_24_unknown_and_broken_schema_safe_stop(self):
        state = initial_state(80, self.policy)
        for bad in (render(state).replace(START, "<!-- langbench-automation-state:v99\n"),
                    render(state).replace('"schema_version":1', '"schema_version":99'),
                    START + "{broken\nlangbench-automation-state:end -->"):
            with self.subTest(body=bad[:60]):
                with self.assertRaises(ValueError):
                    parse_state(bad, 80, self.policy)
                api = FakeGitHub(self.policy, self.facts, bad)
                safe_stop(api, 80, self.policy)
                self.assertTrue(api.dashboard["body"].startswith(bad))
                self.assertIn("SAFE_STOPPED", api.dashboard["body"])


class DashboardTrustRegressions(unittest.TestCase):
    def test_latest_work_edit_revokes_pass_and_unknown_requirements_stop(self):
        policy, facts, report = fixtures()
        passed = record(WORK, report, 102)
        passed["updated_at"] = "2026-10-04T12:00:00Z"
        blocked = copy.deepcopy(report)
        blocked["verdict"] = "BLOCKED"
        edited = record(WORK, blocked, 100)
        edited["updated_at"] = "2026-10-04T12:01:00Z"
        facts["pr_comments"] = [passed, edited]
        self.assertEqual("BLOCKED", evaluate(80, policy, None, facts)["merge_gate"]["status"])
        del policy["requirements"]["artifact_integrity"]
        with self.assertRaisesRegex(ValueError, "requirement"):
            initial_state(80, policy)

    def test_owner_retry_receipts_preserve_key_and_active_identity(self):
        policy, facts, _ = fixtures()
        previous = initial_state(80, policy)
        failed = copy.deepcopy(policy["initial_dispatch"])
        failed["state"] = "FAILED"
        retry = copy.deepcopy(failed)
        retry.update(run_id="actual-retry-task", state="RUNNING", attempt=2, retry_of=failed["run_id"])
        facts["issue_comments"] = [record(RECEIPT, {"schema_version": 1, "repository": REPOSITORY,
            "issue": 80, "dispatch": failed}, 101), record(RECEIPT, {"schema_version": 1,
            "repository": REPOSITORY, "issue": 80, "active": True, "dispatch": retry}, 102)]
        state = evaluate(80, policy, previous, facts)
        self.assertEqual("PASS", state["merge_gate"]["status"])
        self.assertEqual(previous["dedup_key"], state["dedup_key"])
        self.assertEqual("actual-retry-task", state["active_run_id"])
        self.assertEqual(2, len(state["dispatches"]))
        self.assertEqual(state, parse_state(render(state), 80, policy))

    def test_missing_bound_pr_and_multiple_candidates_stop(self):
        policy, facts, _ = fixtures()
        previous = evaluate(80, policy, None, facts)
        facts["pr"] = None
        self.assertEqual("SAFE_STOPPED", evaluate(80, policy, previous, facts)["current_state"])

    def test_sync_artifact_is_digest_checked_and_never_extracted(self):
        _, facts, _ = fixtures()
        sync, _ = run(20, "pull-local-main.yml", 2, MERGE, "push")
        def packed(name, contents):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr(name, contents)
            return stream.getvalue()
        class ArtifactAPI(GitHub):
            def __init__(self, data, digest=None):
                super().__init__("fixture")
                self.data = data
                self.digest = digest or "sha256:" + hashlib.sha256(data).hexdigest()
            def pages(self, path, key=None):
                return [{"id": 40, "name": "local-main-sync-20-attempt1", "expired": False, "digest": self.digest}]
            def request(self, path, method="GET", data=None, raw=False):
                self.asserted_path = path
                return self.data
        api = ArtifactAPI(packed("sync-report.json", '{"status":"success"}'))
        self.assertEqual({"status": "success"}, api.sync_report(sync))
        for api in (ArtifactAPI(packed("../script.py", "untrusted")),
                    ArtifactAPI(packed("sync-report.json", "{}"), "sha256:" + "0" * 64)):
            with self.assertRaises(ValueError):
                api.sync_report(sync)

    def test_wrong_repository_workflow_and_job_identity(self):
        policy, facts, _ = fixtures()
        for field, value in (("workflow_id", 99), ("repository", {"full_name": "attacker/repo"}),
                             ("event", "workflow_dispatch"), ("path", ".github/workflows/fake.yml")):
            candidate = copy.deepcopy(facts)
            candidate["ci_runs"][0][field] = value
            self.assertNotEqual("PASS", evaluate(80, policy, None, candidate)["merge_gate"]["status"])
        facts["jobs"]["10"][0]["head_sha"] = OLD
        self.assertEqual("ERROR", evaluate(80, policy, None, facts)["merge_gate"]["status"])

    def test_missing_public_data_and_work_fields_fail_closed(self):
        policy, facts, report = fixtures()
        facts["jobs"]["10"][0]["steps"] = []
        self.assertNotEqual("PASS", evaluate(80, policy, None, facts)["merge_gate"]["status"])
        del report["blockers"]
        facts["pr_comments"] = [record(WORK, report)]
        self.assertEqual("ERROR", evaluate(80, policy, None, facts)["work_review"]["status"])

    def test_pr_metadata_autoclose_and_changes_requested(self):
        policy, facts, _ = fixtures()
        facts["pr"]["body"] += "Closes #80\n"
        self.assertNotEqual("PASS", evaluate(80, policy, None, facts)["merge_gate"]["status"])
        facts["reviews"] = [{"id": 1, "user": {"id": 9}, "state": "CHANGES_REQUESTED", "commit_id": HEAD}]
        self.assertEqual("BLOCKED", evaluate(80, policy, None, facts)["merge_gate"]["status"])

    def test_schema_type_and_owner_change_cannot_be_silently_migrated(self):
        policy, _, _ = fixtures()
        for field, value in (("schema_version", True), ("requirements", {}), ("dispatch_owners", {}), ("dispatches", [None])):
            state = initial_state(80, policy)
            state[field] = value
            with self.assertRaises(ValueError):
                parse_state(render(state), 80, policy)

    def test_read_failure_revokes_previous_pass(self):
        policy, facts, _ = fixtures()
        state = evaluate(80, policy, None, facts)
        api = FakeGitHub(policy, facts, render(state))
        safe_stop(api, 80, policy)
        stopped = parse_state(api.dashboard["body"], 80, policy)
        self.assertEqual("ERROR", stopped["merge_gate"]["status"])
        self.assertEqual(state["dispatches"], stopped["dispatches"])

    def test_adapter_collects_current_api_facts(self):
        policy, facts, _ = fixtures()
        dashboard, observed = collect(FakeGitHub(policy, facts), 80, policy, None)
        self.assertEqual(5979234464, dashboard["id"])
        self.assertEqual(facts, observed)

    def test_redirect_strips_bearer_token(self):
        req = urllib.request.Request("https://api.github.com/repos/x/y/actions/artifacts/1/zip",
                                     headers={"Authorization": "Bearer secret"})
        redirected = SafeRedirect().redirect_request(req, None, 302, "", {}, "https://example.blob.core.windows.net/file?signature=example")
        self.assertFalse(redirected.has_header("Authorization"))
        with self.assertRaises(ValueError):
            SafeRedirect().redirect_request(req, None, 302, "", {}, "https://attacker.invalid/file")

    def test_no_dispatch_methods_and_workflow_trust_boundary(self):
        api = GitHub("fake")
        for endpoint in ("/actions/workflows/x/dispatches", "/actions/runs/1/rerun", "/actions/runs/1/cancel", "/pulls/81/merge"):
            with self.assertRaises(ValueError):
                api.request(api.root + endpoint, "POST", {})
        workflow = (ROOT / ".github/workflows/automation-dashboard.yml").read_text(encoding="utf-8")
        self.assertIn("ref: refs/heads/main", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("github.event.pull_request.head", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("Prepare Windows function-call analysis artifact", workflow)
        self.assertNotIn("pull_request_review:", workflow)
        self.assertIn("github.event.sender.login", workflow)
        bridge = (ROOT / ".github/workflows/automation-dashboard-review-event.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request_review:", bridge)
        self.assertNotIn("write", bridge.split("permissions:")[1])
        self.assertNotIn("actions/checkout", bridge)


class GateEvidenceFixRegressions(unittest.TestCase):
    """R1–R3 from Work review 5405787735; F1 intentionally remains deferred."""
    def setUp(self):
        self.policy, self.facts, self.report = fixtures()

    def completed_facts(self):
        self.facts["pr"].update(merged=True, state="closed", merge_commit_sha=MERGE,
                                merged_at=NOW, merged_by=self.policy["owner"])
        value, jobs = run(20, "pull-local-main.yml", 2, MERGE, "push", ["verify-merge", "pull-main"])
        self.facts["sync_runs"] = [value]
        self.facts["jobs"]["20"] = jobs
        self.facts["sync_reports"]["20"] = {
            "schema_version": 1, "repository": REPOSITORY, "pr": 81, "pr_head_sha": HEAD,
            "merge_sha": MERGE, "target_sha": MERGE, "before_sha": OLD, "after_sha": MERGE,
            "run_id": "20", "run_attempt": 1, "status": "success", "protected_preserved": True, "protected_files": 9}
        self.facts["issue_comments"] = [record(SMOKE, {"schema_version": 1, "repository": REPOSITORY, "issue": 80,
            "pr": 81, "merge_sha": MERGE, "dashboard_comment_id": 5979234464,
            "sync_run_id": 20, "observed_state": "LOCAL_SYNCED", "status": "PASS"})]
        self.assertEqual("COMPLETED", evaluate(80, self.policy, None, self.facts)["current_state"])

    def race(self, mutate):
        api = FakeGitHub(self.policy, self.facts)
        def hook(path, method):
            if method == "PATCH":
                mutate(api.facts)
                api.hook = None
        api.hook = hook
        self.assertEqual("RACE_BLOCKED", reconcile(api, 80, self.policy, NOW))
        state = parse_state(api.dashboard["body"], 80, self.policy)
        self.assertEqual("SAFE_STOPPED", state["current_state"])
        self.assertEqual("STALE", state["merge_gate"]["status"])
        self.assertEqual("STALE", state["completion_gate"]["status"])
        self.assertEqual(["PATCH", "PATCH"], [write[0] for write in api.writes])
        self.assertEqual([self.policy["initial_dispatch"]], state["dispatches"])
        return state

    def test_r1_ci_retry_during_patch_revokes_ready_pass(self):
        def retry(facts):
            facts["ci_runs"][0].update(run_attempt=2, status="in_progress", conclusion=None)
        state = self.race(retry)
        self.assertEqual("PENDING", state["required_ci"]["status"])

    def test_r1_ci_job_change_without_head_or_run_change_revokes_pass(self):
        state = self.race(lambda facts: facts["jobs"]["10"][1].update(conclusion="failure"))
        self.assertEqual("BLOCKED", state["required_ci"]["status"])

    def test_r1_work_update_during_patch_revokes_pass(self):
        report = copy.deepcopy(self.report)
        report["verdict"] = "BLOCKED"
        state = self.race(lambda facts: facts.update(pr_comments=[record(WORK, report)]))
        self.assertEqual("BLOCKED", state["work_review"]["status"])

    def test_r1_condition_run_change_during_patch_revokes_pass(self):
        # Even optional external evidence fetched for an authenticated report is
        # included in the post-write fingerprint. No F1 target-phase change.
        value, _ = run(30, "measurement-validation-windows.yml", 3, HEAD, "workflow_dispatch")
        value["head_branch"] = "main"
        self.policy["requirements"]["windows_validation"] = "REQUIRED"
        self.report["conditions"]["windows_validation"] = {"status": "PASS", "head_sha": HEAD, "run_id": 30}
        self.facts["pr_comments"] = [record(WORK, self.report)]
        self.facts["condition_runs"]["30"] = value
        self.assertEqual("PASS", evaluate(80, self.policy, None, self.facts)["merge_gate"]["status"])
        self.race(lambda facts: facts["condition_runs"]["30"].update(conclusion="failure"))

    def test_r1_sync_attempt_change_during_patch_revokes_completed(self):
        self.completed_facts()
        def retry(facts):
            facts["sync_runs"][0].update(run_attempt=2, status="in_progress", conclusion=None)
        state = self.race(retry)
        self.assertEqual("PENDING", state["local_sync"]["status"])

    def test_r1_sync_safety_report_change_during_patch_revokes_completed(self):
        self.completed_facts()
        state = self.race(lambda facts: facts["sync_reports"]["20"].update(protected_preserved=False))
        self.assertEqual("ERROR", state["local_sync"]["status"])

    def test_r1_start_and_retry_event_invalidation_path(self):
        workflow = (ROOT / ".github/workflows/automation-dashboard.yml").read_text(encoding="utf-8")
        self.assertIn("types: [requested, in_progress, completed]", workflow)
        self.assertIn("GitHub does not emit requested for reruns", workflow)
        self.assertIn("ref: refs/heads/main", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_r2_completion_requires_successful_ci_in_all_states(self):
        cases = {
            "failure": lambda facts: facts["ci_runs"][0].update(conclusion="failure"),
            "pending_retry": lambda facts: facts["ci_runs"][0].update(run_attempt=2, status="in_progress", conclusion=None),
            "stale": lambda facts: facts["ci_runs"][0].update(head_sha=OLD),
            "missing": lambda facts: facts.update(ci_runs=[]),
            "unknown_status": lambda facts: facts["ci_runs"][0].update(status=None, conclusion=None),
            "unknown_conclusion": lambda facts: facts["ci_runs"][0].update(conclusion=None),
            "missing_job": lambda facts: facts["jobs"].update({"10": []}),
        }
        self.completed_facts()
        for name, mutate in cases.items():
            with self.subTest(case=name):
                facts = copy.deepcopy(self.facts)
                mutate(facts)
                state = evaluate(80, self.policy, None, facts)
                self.assertNotEqual("PASS", state["required_ci"]["status"])
                self.assertNotEqual("PASS", state["completion_gate"]["status"])
                self.assertNotEqual("COMPLETED", state["current_state"])
                self.assertEqual("PASS", state["local_sync"]["status"])

    def test_r2_completion_requires_public_data_verification(self):
        self.completed_facts()
        for conclusion in ("failure", "in_progress", None):
            with self.subTest(conclusion=conclusion):
                facts = copy.deepcopy(self.facts)
                facts["jobs"]["10"][0]["steps"][0]["conclusion"] = conclusion
                state = evaluate(80, self.policy, None, facts)
                self.assertEqual("PASS", state["required_ci"]["status"])
                self.assertNotEqual("PASS", state["public_data"]["status"])
                self.assertNotEqual("PASS", state["completion_gate"]["status"])
                self.assertNotEqual("COMPLETED", state["current_state"])

    def test_r3_malformed_trusted_record_main_revokes_existing_pass(self):
        mutations = {
            "conditions_list": lambda report: report.update(conditions=["broken"]),
            "conditions_string": lambda report: report.update(conditions="broken"),
            "conditions_null": lambda report: report.update(conditions=None),
            "conditions_missing": lambda report: report.pop("conditions"),
            "condition_value_list": lambda report: report.update(conditions={"artifact_integrity": ["broken"]}),
            "schema_unknown": lambda report: report.update(schema_version=99),
            "head_invalid": lambda report: report.update(head_sha="broken"),
            "blockers_missing": lambda report: report.pop("blockers"),
            "api_id_invalid": lambda report: report.update(conditions={"artifact_integrity": {"status": "PASS", "head_sha": HEAD, "run_id": "untrusted"}}),
        }
        previous = evaluate(80, self.policy, None, self.facts)
        self.assertEqual("PASS", previous["merge_gate"]["status"])
        for name, mutate in mutations.items():
            with self.subTest(case=name):
                facts, report = copy.deepcopy(self.facts), copy.deepcopy(self.report)
                mutate(report)
                facts["pr_comments"] = [record(WORK, report)]
                api = FakeGitHub(self.policy, facts, render(previous))
                output = io.StringIO()
                with patch("tools.update_automation_dashboard.GitHub", return_value=api), \
                     patch.dict(os.environ, {"GH_TOKEN": "fixture-token", "GITHUB_REPOSITORY": REPOSITORY}), \
                     patch("sys.argv", ["update_automation_dashboard.py", "--config", str(ROOT / ".github/automation-dashboard.json")]), \
                     redirect_stdout(output):
                    self.assertEqual(1, main())
                stopped = parse_state(api.dashboard["body"], 80, self.policy)
                self.assertEqual("SAFE_STOPPED", stopped["current_state"])
                self.assertEqual("ERROR", stopped["merge_gate"]["status"])
                self.assertEqual("ERROR", stopped["completion_gate"]["status"])
                self.assertEqual(previous["dispatches"], stopped["dispatches"])
                self.assertIn("Work", output.getvalue())
                self.assertNotIn("fixture-token", output.getvalue())

    def test_r3_other_work_identity_cannot_select_api_ids(self):
        for field, value in (("automation_id", "unregistered"), ("repository", "other/repo"), ("issue", 999), ("pr", 999), ("kind", "not-work")):
            with self.subTest(field=field):
                facts, report = copy.deepcopy(self.facts), copy.deepcopy(self.report)
                report[field] = value
                report["conditions"] = {"artifact_integrity": {"status": "PASS", "head_sha": HEAD, "run_id": 999}}
                facts["pr_comments"] = [record(WORK, report)]
                # FakeGitHub has no route for run 999: any read would fail.
                _, collected = collect(FakeGitHub(self.policy, facts), 80, self.policy, None)
                self.assertEqual({}, collected["condition_runs"])

    def test_r3_post_write_work_corruption_main_revokes_published_pass(self):
        api = FakeGitHub(self.policy, self.facts)
        def corrupt(path, method):
            if method == "PATCH":
                broken = copy.deepcopy(self.report)
                broken["conditions"] = ["broken"]
                api.facts["pr_comments"] = [record(WORK, broken)]
                api.hook = None
        api.hook = corrupt
        with patch("tools.update_automation_dashboard.GitHub", return_value=api), \
             patch.dict(os.environ, {"GH_TOKEN": "fixture-token", "GITHUB_REPOSITORY": REPOSITORY}), \
             patch("sys.argv", ["update_automation_dashboard.py", "--config", str(ROOT / ".github/automation-dashboard.json")]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(1, main())
        self.assertEqual("PASS", parse_state(api.writes[0][2]["body"], 80, self.policy)["merge_gate"]["status"])
        stopped = parse_state(api.dashboard["body"], 80, self.policy)
        self.assertEqual("SAFE_STOPPED", stopped["current_state"])
        self.assertEqual("ERROR", stopped["merge_gate"]["status"])
        self.assertEqual("ERROR", stopped["completion_gate"]["status"])


if __name__ == "__main__":
    unittest.main()
