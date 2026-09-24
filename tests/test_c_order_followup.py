import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.c_order_followup import build_public, markdown, slow_ranges, validate_followup_monitor
from tools.summarize_c_order_diagnostic import followup_plan, statistics


class COrderFollowupTests(unittest.TestCase):
    def test_plan_balances_every_order_monitor_and_position(self):
        plan = followup_plan()
        self.assertEqual(len(plan), 40)
        self.assertEqual(sum(plan[2 * i]["order"] == "A" for i in range(20)), 10)
        self.assertEqual(sum(plan[2 * i]["order"] == "B" for i in range(20)), 10)
        for pair in range(1, 21):
            runs = [item for item in plan if item["pair"] == pair]
            self.assertEqual([item["position"] for item in runs], [1, 2])
            self.assertEqual({item["order"] for item in runs}, {"A", "B"})
            self.assertEqual(sum(item["monitored"] for item in runs), 1)
        for order in ("A", "B"):
            for monitored in (False, True):
                condition = [item for item in plan if item["order"] == order and item["monitored"] == monitored]
                self.assertEqual(len(condition), 10)
                self.assertEqual(sum(item["position"] == 1 for item in condition), 5)
                self.assertEqual(sum(item["position"] == 2 for item in condition), 5)

    @staticmethod
    def failed_record():
        plan = followup_plan()
        runs = []
        for number, item in enumerate(plan, 1):
            monitored = item["monitored"]
            runs.append({**item, "number": number, "started_at": "start", "ended_at": "end",
                         "status": "failed", "c_measurement_status": "failed", "trace_status": "failed",
                         "monitor_status": "failed" if monitored else "not_planned",
                         "monitor_launch_status": "failed" if monitored else "not_planned",
                         "monitor_exit_status": "not_started" if monitored else "not_planned",
                         "monitor_file_status": "missing" if monitored else "not_planned",
                         "monitor_validation_status": "not_available" if monitored else "not_planned",
                         "reason_code": "C_MEASUREMENT_FAILED", "monitor_reason_code": "MONITOR_FILE_MISSING" if monitored else None})
        return {"schema_version": "3.0", "git_head": "abc", "c_source_sha256": "0" * 64,
                "plan": plan, "runs": runs}

    def test_final_states_keep_c_and_monitor_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            record = self.failed_record()
            (folder / "plan.json").write_text(json.dumps(record["plan"]), encoding="utf-8")
            (folder / "runs.json").write_text(json.dumps(record), encoding="utf-8")
            public = build_public(record, folder)
            self.assertEqual(len(public["runs"]), 40)
            self.assertEqual(public["runs"][0]["monitor_status"], "failed")
            self.assertEqual(public["runs"][1]["monitor"]["status"], "not_planned")
            self.assertIn("CPU観測なし", markdown(public))
            self.assertIn("取得失敗", markdown(public))
            early = copy.deepcopy(record)
            early["runs"][0]["monitor_validation_status"] = "pending"
            with self.assertRaisesRegex(ValueError, "not finalized"):
                build_public(early, folder)
            early = copy.deepcopy(record)
            early["runs"][0]["status"] = "success"
            with self.assertRaisesRegex(ValueError, "C/trace status differs"):
                build_public(early, folder)
            early = copy.deepcopy(record)
            early["runs"][0]["monitor_status"] = "recorded"
            for key in ("monitor_launch_status", "monitor_exit_status", "monitor_file_status", "monitor_validation_status"):
                early["runs"][0][key] = "success"
            with self.assertRaisesRegex(ValueError, "monitor source missing"):
                build_public(early, folder)
            (folder / "run-01-monitor.json").write_text("{invalid", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                build_public(early, folder)
            monitor = {"schema_version": "1.0", "clock": "windows_qpc", "frequency_hz": 1_000_000,
                       "requested_interval_ms": 20, "started_qpc": 0, "ended_qpc": 100,
                       "observations": [{"start_qpc": 1, "probe_start_qpc": 1, "end_qpc": 2,
                                         "probe_duration_qpc": 1, "cpu_busy_percent": None,
                                         "error": "first probe has no preceding CPU time"},
                                        {"start_qpc": 2, "probe_start_qpc": 3, "end_qpc": 4,
                                         "probe_duration_qpc": 1, "cpu_busy_percent": 25.0,
                                         "error": None}]}
            (folder / "run-01-monitor.json").write_text(json.dumps(monitor), encoding="utf-8")
            public = build_public(early, folder)
            self.assertEqual(public["runs"][0]["c_measurement_status"], "failed")
            self.assertEqual(public["runs"][0]["monitor_status"], "recorded")
            self.assertEqual(public["runs"][0]["monitor"]["failed_observations"], 1)
            empty = copy.deepcopy(monitor)
            empty["observations"] = empty["observations"][:1]
            with self.assertRaisesRegex(ValueError, "no valid CPU observations"):
                validate_followup_monitor(None, empty)
            monitor["requested_interval_ms"] = 25
            with self.assertRaisesRegex(ValueError, "fixed conditions"):
                validate_followup_monitor(None, monitor)

    def test_table_recalculates_slow_runs_samples_positions_and_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            record = self.failed_record()
            (folder / "plan.json").write_text(json.dumps(record["plan"]), encoding="utf-8")
            (folder / "runs.json").write_text(json.dumps(record), encoding="utf-8")
            public = build_public(record, folder)
        run = public["runs"][0]
        samples = [0.1] * 50
        samples[2:4] = [0.2, 0.3]
        timed = [{"number": i + 1, "start_qpc": 100 + i * 100, "end_qpc": 200 + i * 100,
                  "sample_ms": value, "coverage": {"coverage": "missing"}} for i, value in enumerate(samples)]
        run.update(status="success", c_measurement_status="success", trace_status="success",
                   cases={"direct": {"samples_ms": samples, **statistics(samples), "timed_samples": timed}})
        table = markdown(public)
        self.assertIn("| A | あり | 10 | 1 | 1 | 0 |", table)
        self.assertIn("| 1 | 3 | 0.2 | 300–400 | 取得失敗 |", table)
        self.assertIn("3–4", table)
        self.assertEqual(slow_ranges(samples), "3–4")
        run["cases"]["direct"]["median_ms"] += 1
        with self.assertRaisesRegex(ValueError, "published statistics differ"):
            markdown(public)

    def test_published_series_tables_recompute_without_private_paths(self):
        root = Path(__file__).resolve().parents[1] / "artifacts/c-order-followup"
        for prefix, expected_success in (("attempt-01-", 0), ("", 40)):
            with self.subTest(prefix=prefix):
                content = (root / f"{prefix}public-data.json").read_text(encoding="utf-8")
                public = json.loads(content)
                self.assertEqual(public["plan"], followup_plan())
                self.assertEqual(len(public["runs"]), 40)
                self.assertEqual(sum(run["status"] == "success" for run in public["runs"]), expected_success)
                self.assertEqual(markdown(public), (root / f"{prefix}summary.md").read_text(encoding="utf-8"))
                self.assertNotIn("C:\\", content)
                self.assertNotIn("tetsu", content)
                self.assertNotIn("compile_command", content)
                for run in public["runs"]:
                    for key in ("source_result", "source_trace"):
                        self.assertEqual(len(run[key]["sha256"]), 64)
                    if run["monitored"]:
                        self.assertEqual(len(run["source_monitor"]["sha256"]), 64)
                    if run["status"] == "success":
                        for case in ("direct", "function_call"):
                            item = run["cases"][case]
                            self.assertEqual(len(item["timed_samples"]), 50)
                            for key, value in statistics(item["samples_ms"]).items():
                                self.assertEqual(item[key], value)


if __name__ == "__main__":
    unittest.main()
