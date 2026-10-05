"""Issue #83 display-only regressions. All review/run/PR fixtures are synthetic."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.test_automation_dashboard import (
    FakeGitHub, HEAD, OLD, MERGE, NOW, fixtures,
)
from tools.automation_dashboard import (
    END, REPOSITORY, START, DISPATCH, STATUSES, evaluate, initial_state, parse_state, render, result,
)
from tools.automation_dashboard_display import (
    DISPATCH_LABELS, STATE_LABELS, STATUS_LABELS, plain, reference, updated_time,
)
from tools.update_automation_dashboard import reconcile, safe_stop


class DashboardDisplayTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.facts, _ = fixtures()
        self.state = evaluate(80, self.policy, None, self.facts)
        self.state["last_updated"] = NOW

    def visible(self, state=None):
        return render(state or self.state).split(START)[0]

    def test_state_and_dispatch_codes_from_existing_implementation(self):
        self.assertEqual(STATUSES, set(STATUS_LABELS))
        self.assertEqual(DISPATCH, set(DISPATCH_LABELS))
        for code, label in STATE_LABELS.items():
            with self.subTest(code=code):
                self.state["current_state"] = code
                self.assertIn(plain(code) + " — " + label, self.visible())
        for code, label in DISPATCH_LABELS.items():
            with self.subTest(code=code):
                self.state["dispatch_state"] = code
                self.assertIn(plain(code) + " — " + label, self.visible())
        self.state["current_state"] = "FUTURE_UNKNOWN"
        self.state["merge_gate"] = result("FUTURE_GATE", "not a pass")
        self.assertIn(plain("FUTURE_UNKNOWN") + " — 説明未定義", self.visible())
        self.assertIn(plain("FUTURE_GATE") + " — 説明未定義", self.visible())

    def test_status_reason_and_missing_values_are_distinct(self):
        for code, label in STATUS_LABELS.items():
            with self.subTest(code=code):
                self.state["work_review"] = result(code, "original reason")
                body = self.visible()
                self.assertIn(plain(code) + " — " + label, body)
                self.assertIn("理由: original reason", body)
                self.assertIn("対象head SHA: 未取得", body)
                self.assertIn("Work結果comment ID: 未取得", body)
        missing = initial_state(80, self.policy)
        body = self.visible(missing)
        self.assertIn("| PR | 未取得 |", body)
        self.assertIn("| Dashboard最終更新 | 未取得 |", body)
        self.assertIn("今回の承認済み範囲では不要", body)
        self.assertIn("| live smoke | REQUIRED — 今回の必須条件 / 未取得 |", body)
        self.assertNotIn("None", body)

    def test_sections_are_ordered_and_blockers_unconfirmed_stay_visible(self):
        self.state["blockers"] = ["need owner", {"summary": "needs confirmation", "pr": 81}]
        self.state["work_review"] = result("PENDING", "review not received")
        body = self.visible()
        names = ["### 状態・Gate・blocker", "### Issue・PR・SHA", "### Workレビュー・CI・公開データ",
                 "### 正式同期・live smoke・必要条件", "### 担当・dispatch", "### 診断詳細・履歴・更新時刻"]
        positions = [body.index(name) for name in names]
        self.assertEqual(sorted(positions), positions)
        outside = body.split("<details>")[0]
        for text in ("need owner", "needs confirmation", "review not received", plain("FOLLOW_UP")):
            self.assertIn(text, outside)
        self.assertIn("https://github.com/" + REPOSITORY + "/pull/81", outside)

    def test_completed_and_blocked_gate_keep_original_reason(self):
        self.state.update(current_state="COMPLETED", merge_state="MERGED", merge_sha=MERGE)
        self.state["merge_gate"] = result("BLOCKED", "PR already merged; no merge authorization")
        self.state["completion_gate"] = result("PASS", "All required evidence is current and successful")
        original = copy.deepcopy(self.state)
        body = self.visible()
        self.assertIn("COMPLETED — 必須完了条件が成立", body)
        self.assertIn("BLOCKED — 阻害条件あり", body)
        self.assertIn("PR already merged; no merge authorization", body)
        self.assertIn("マージ済みのため、新たなマージ許可の対象外", body)
        self.assertIn("併存します", body)
        self.assertEqual(original, parse_state(render(self.state), 80, self.policy))

    def test_heads_merge_sync_attempt_and_work_reference_are_separate(self):
        self.state["work_review"] = result("STALE", "old review", head_sha=OLD, comment_id=123)
        self.state["ci_ubuntu"] = result("STALE", "old CI", head_sha=OLD, run_id=456, run_attempt=2)
        self.state.update(merge_sha=MERGE, local_sync_target_sha=MERGE)
        self.state["local_sync"] = result("PENDING", "sync waiting", target_sha=MERGE, run_id="789", run_attempt=3)
        body = self.visible()
        root = "https://github.com/" + REPOSITORY
        for path in ("commit/" + HEAD, "commit/" + OLD, "commit/" + MERGE,
                     "pull/81#issuecomment-123", "actions/runs/456", "actions/runs/789", "issues/80", "pull/81"):
            self.assertIn(root + "/" + path, body)
        self.assertIn("現在PR headと不一致", body)
        self.assertIn("run attempt: 2", body)
        self.assertIn("run attempt: 3", body)
        self.assertIn("| 同期target SHA | [" + MERGE, body)
        self.assertIn("| 現在PR head SHA | [" + HEAD, body)
        self.assertIn("| merge SHA | [" + MERGE, body)
        self.state["ci_ubuntu"].pop("head_sha")
        row = next(x for x in self.visible().splitlines() if x.startswith("| Ubuntu CI |"))
        self.assertIn("対象head SHA: 未取得", row)
        self.assertIn("照合未確認", row)
        self.assertNotIn("一致 /", row)

    def test_link_identity_validation_and_cloud_task_never_guessed(self):
        for value in (None, 0, -1, True, "0", "01", "../1", "1?token=secret", "https://evil.test/1"):
            for kind in ("issue", "pr", "run", "comment", "commit"):
                with self.subTest(value=value, kind=kind):
                    self.assertNotIn("](https://", reference(self.state, REPOSITORY, kind, value))
        other = {**self.state, "repository": "other/repo"}
        self.assertNotIn("](https://", reference(other, REPOSITORY, "pr", 81))
        self.assertNotIn("](https://", reference({**self.state, "pr": None}, REPOSITORY, "comment", 123))
        self.state["active_run_id"] = "task_e_123"
        self.state["work_review"]["url"] = "https://evil.test/steal"
        self.state["work_review"]["reason"] = "www.evil.test test@evil.test"
        body = self.visible()
        self.assertIn(plain("task_e_123"), body)
        self.assertNotIn("https://evil.test", body)
        self.assertNotIn("www.evil.test", body)
        self.assertNotIn("test@evil.test", body)
        self.assertNotIn("chatgpt.com", body)

    def test_timezone_conversion_and_missing_invalid_times(self):
        for value, expected in (("2026-10-05T15:30:00Z", "2026-10-06T00:30:00+09:00"),
                                ("2026-12-31T18:00:00+00:00", "2027-01-01T03:00:00+09:00"),
                                ("2026-10-05T23:30:00-04:00", "2026-10-06T12:30:00+09:00")):
            self.assertEqual(plain(value) + "（元値） / JST: " + plain(expected), updated_time(value))
        for value in ("bad", "2026-02-30T00:00:00Z", "2026-10-05T12:00:00", "2026-10-05", "2026-10-05T12:00:00+24:00"):
            self.assertEqual(plain(value) + " / JST: 解析不能", updated_time(value))
        for value in (None, ""):
            self.assertEqual("未取得", updated_time(value))
        self.assertNotIn("最終監視成功", self.visible())
        self.assertNotIn("最終作業進捗", self.visible())

    def test_injection_determinism_round_trip_and_exact_machine_payload(self):
        hostile = "\r\n| fake | PASS |\r</details><script>alert(1)</script> [x](https://evil.test) `* \\\n" + START + END
        self.state["purpose"] = hostile
        self.policy["purpose"] = hostile
        self.state["blockers"] = [hostile]
        self.state["follow_up"] = [{"summary": hostile, "head_sha": OLD, "url": "https://evil.test"}]
        self.state["work_review"]["reason"] = hostile
        self.state["work_review"]["extra"] = {"hostile": hostile}
        original = copy.deepcopy(self.state)
        rendered = render(self.state)
        self.assertEqual(rendered, render(self.state))
        self.assertEqual(original, self.state)
        self.assertEqual(original, parse_state(rendered, 80, self.policy))
        self.assertEqual(1, rendered.count(START))
        self.assertEqual(1, rendered.count(END))
        visible = self.visible()
        self.assertEqual(1, visible.count("<details>"))
        self.assertEqual(1, visible.count("</details>"))
        for bad in ("<script>", "https://evil.test", "| fake | PASS |", "[x](", "\r"):
            self.assertNotIn(bad, visible)
        payload = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")
        self.assertEqual(payload, rendered.split(START)[1].split(END)[0])

    def test_gate_transition_and_dedup_do_not_change_on_render_or_reprocessing(self):
        before = evaluate(80, self.policy, self.state, self.facts)
        after = evaluate(80, self.policy, parse_state(render(self.state), 80, self.policy), self.facts)
        self.assertEqual(before, after)
        api = FakeGitHub(self.policy, self.facts, render(self.state))
        self.assertEqual("NO_OP", reconcile(api, 80, self.policy, "2027-01-01T00:00:00+00:00"))
        self.assertEqual([], api.writes)
        self.assertEqual(NOW, parse_state(api.dashboard["body"], 80, self.policy)["last_updated"])

    def test_unknown_and_broken_schema_keep_existing_safe_stop(self):
        for body in (render(self.state).replace(START, "<!-- langbench-automation-state:v99\n"),
                     render(self.state).replace('"schema_version":1', '"schema_version":99'),
                     "## LangBench-Live Automation Dashboard\n" + START + "{broken" + END):
            with self.subTest(body=body[:70]):
                api = FakeGitHub(self.policy, self.facts, body)
                with self.assertRaises(ValueError):
                    reconcile(api, 80, self.policy, NOW)
                safe_stop(api, 80, self.policy)
                self.assertTrue(api.dashboard["body"].startswith(body))
                self.assertIn("SAFE_STOPPED", api.dashboard["body"])
                self.assertIn("Completion Gate: ERROR", api.dashboard["body"])

    def test_renderer_has_no_clock_or_network_access(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
             patch("tools.update_automation_dashboard.datetime") as clock:
            render(self.state)
            clock.now.assert_not_called()

    def test_workflow_script_entry_point_imports_display_helper(self):
        # The real workflow executes tools/update_automation_dashboard.py directly,
        # so only the tools directory (not the package root) may be on sys.path.
        script = (
            "import sys, os, json; sys.path.insert(0, os.getcwd()); "
            "import update_automation_dashboard, automation_dashboard as dashboard; "
            "policy=json.load(open('../.github/automation-dashboard.json', encoding='utf-8'))['issues']['80']; "
            "print(dashboard.render(dashboard.initial_state(80, policy)))"
        )
        output = subprocess.check_output(
            [sys.executable, "-I", "-X", "utf8", "-B", "-c", script],
            cwd=Path(__file__).resolve().parents[1] / "tools", encoding="utf-8",
        )
        self.assertIn("Dashboard最終更新", output)
        self.assertEqual(initial_state(80, self.policy), parse_state(output, 80, self.policy))


if __name__ == "__main__":
    unittest.main()
