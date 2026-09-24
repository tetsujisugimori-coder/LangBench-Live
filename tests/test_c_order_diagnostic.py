import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from tools.summarize_c_order_diagnostic import (build_public, coverage, fixed_plan, markdown,
                                               monitor_summary, statistics, utc_from_qpc, validate_trace)
from tools.validate_result_json import validate
from tests.test_result_schema import function_call_document


ROOT = Path(__file__).resolve().parents[1]


class COrderDiagnosticTests(unittest.TestCase):
    def test_fixed_monitor_plan_balances_order_and_limits_position_bias(self):
        plan = fixed_plan()
        self.assertEqual(len(plan), 20)
        for order in ("A", "B"):
            self.assertEqual(sum(item["order"] == order and item["monitored"] for item in plan), 5)
            self.assertEqual(sum(item["order"] == order and not item["monitored"] for item in plan), 5)
        self.assertEqual(sum(item["position"] == 1 and item["monitored"] for item in plan), 6)
        self.assertEqual(sum(item["position"] == 2 and item["monitored"] for item in plan), 4)
        for pair in range(1, 11):
            self.assertEqual(sum(item["monitored"] for item in plan if item["pair"] == pair), 1)

    def test_clock_alignment_sample_order_and_missing_cpu_data(self):
        document = function_call_document("c")
        document["execution"]["measurement_order"] = ["direct", "function_call"]
        for case in ("direct", "function_call"):
            document["results"][case]["samples_ms"] = [0.1] * 50
        trace = {"clock": "windows_qpc", "frequency_hz": 1_000_000,
                 "anchor": {"filetime_100ns": 133_000_000_000_000_000,
                            "qpc_before": 900, "qpc_after": 1100},
                 "measurement_order": ["direct", "function_call"], "cases": {}}
        for offset, case in ((2000, "direct"), (10000, "function_call")):
            trace["cases"][case] = {"start_qpc": offset - 10, "end_qpc": offset + 50 * 120,
                                    "samples": [{"number": i + 1, "start_qpc": offset + i * 120,
                                                 "end_qpc": offset + i * 120 + 100, "sample_ms": 0.1}
                                                for i in range(50)]}
        validate_trace(trace, document)
        self.assertEqual((datetime.fromisoformat(utc_from_qpc(2000, trace)) -
                          datetime.fromisoformat(utc_from_qpc(1000, trace))).total_seconds(), 0.001)
        monitor = {"clock": "windows_qpc", "frequency_hz": 1_000_000,
                   "requested_interval_ms": 20,
                   "observations": [{"start_qpc": 1950, "probe_start_qpc": 2100,
                                     "end_qpc": 2200, "probe_duration_qpc": 100,
                                     "cpu_busy_percent": 75.0, "error": None},
                                    {"start_qpc": 2200, "probe_start_qpc": 2300,
                                     "end_qpc": 2400, "probe_duration_qpc": 100,
                                     "cpu_busy_percent": None, "error": "GetSystemTimes failed"}]}
        summary = monitor_summary(trace, monitor)
        self.assertEqual((summary["valid_observations"], summary["failed_observations"]), (1, 1))
        self.assertEqual(coverage(2000, 2100, summary, 1_000_000)["valid_cpu_observations"], 1)
        self.assertEqual(coverage(2300, 2400, summary, 1_000_000)["coverage"], "missing")
        self.assertEqual(coverage(2000, 2100, {"status": "not_planned"}, 1_000_000)["coverage"], "not_monitored")
        bad = copy.deepcopy(trace)
        bad["cases"]["direct"]["samples"][1]["number"] = 1
        with self.assertRaisesRegex(ValueError, "sample order"):
            validate_trace(bad, document)
        bad = copy.deepcopy(trace)
        bad["frequency_hz"] = 2_000_000
        with self.assertRaisesRegex(ValueError, "duration differs"):
            validate_trace(bad, document)
        bad_monitor = copy.deepcopy(monitor)
        bad_monitor["frequency_hz"] = 2_000_000
        with self.assertRaisesRegex(ValueError, "cannot be compared"):
            monitor_summary(trace, bad_monitor)

    def test_reverse_result_is_excluded_from_normal_validation(self):
        document = function_call_document("c")
        document["execution"]["measurement_order"] = ["function_call", "direct"]
        self.assertTrue(validate(document, Path("reverse.json")))
        self.assertFalse(validate(document, Path("reverse.json"), allow_diagnostic_order=True))
        document["execution"]["measurement_order"] = ["direct", "function_call"]
        self.assertFalse(validate(document, Path("direct.json")))

    def test_statistics_use_input_order_and_cutoff_is_descriptive(self):
        samples = [0.1] * 25 + [0.3] * 25
        self.assertEqual(statistics(samples), {"median_ms": 0.2,
            "first_25_median_ms": 0.1, "last_25_median_ms": 0.3,
            "at_least_0_2_ms": 25})

    def test_failed_attempt_is_recorded_without_success_samples(self):
        record = {"git_head": "abc", "c_source_sha256": "0" * 64,
                  "runs": [{"order": "A", "started_at": "start", "ended_at": "end",
                            "status": "failed", "reason_code": "RUN_FAILED"}]}
        public = build_public(record, ROOT)
        self.assertEqual(public["runs"][0]["status"], "failed")
        self.assertNotIn("cases", public["runs"][0])
        record["runs"][0]["order"] = "B"
        with self.assertRaisesRegex(ValueError, "fixed AB/BA plan"):
            build_public(record, ROOT)

    def test_monitor_plan_cannot_be_changed_after_results(self):
        plan = fixed_plan()
        record = {"schema_version": "2.0", "git_head": "abc", "c_source_sha256": "0" * 64,
                  "plan": plan, "runs": [{**plan[0], "started_at": "start", "ended_at": "end",
                                            "status": "failed", "reason_code": "RUN_FAILED",
                                            "monitor_status": "failed"}]}
        self.assertEqual(build_public(record, ROOT)["runs"][0]["monitor_status"], "failed")
        record["runs"][0]["monitored"] = False
        with self.assertRaisesRegex(ValueError, "fixed plan"):
            build_public(record, ROOT)

    def test_current_published_table_recomputes_and_has_no_private_paths(self):
        public_path = ROOT / "artifacts/c-order-monitor/public-data.json"
        table_path = ROOT / "artifacts/c-order-monitor/summary.md"
        content = public_path.read_text(encoding="utf-8")
        public = json.loads(content)
        self.assertEqual(public["plan"], fixed_plan())
        self.assertEqual(len(public["runs"]), 20)
        self.assertEqual(sum(run["status"] == "success" for run in public["runs"]), 20)
        self.assertNotIn("C:\\", content)
        self.assertNotIn("Users\\", content)
        for run in public["runs"]:
            for case in ("direct", "function_call"):
                item = run["cases"][case]
                self.assertEqual(len(item["timed_samples"]), 50)
                self.assertEqual([sample["number"] for sample in item["timed_samples"]], list(range(1, 51)))
                self.assertEqual([sample["sample_ms"] for sample in item["timed_samples"]], item["samples_ms"])
                for field, value in statistics(item["samples_ms"]).items():
                    self.assertEqual(item[field], value)
        self.assertEqual(markdown(public), table_path.read_text(encoding="utf-8"))

    def test_published_table_recomputes_from_all_samples(self):
        for prefix in ("", "pilot-"):
            with self.subTest(prefix=prefix):
                public_path = ROOT / f"artifacts/c-order-diagnostic/{prefix}public-data.json"
                table_path = ROOT / f"artifacts/c-order-diagnostic/{prefix}summary.md"
                public = json.loads(public_path.read_text(encoding="utf-8"))
                self.assertEqual(len(public["runs"]), 20)
                self.assertEqual([run["order"] for run in public["runs"]], public["plan"])
                self.assertEqual(sum(run["order"] == "A" for run in public["runs"]), 10)
                self.assertEqual(sum(run["order"] == "B" for run in public["runs"]), 10)
                for run in public["runs"]:
                    self.assertEqual(run["measurement_order"], ["direct", "function_call"] if run["order"] == "A" else ["function_call", "direct"])
                    if run["status"] == "success":
                        self.assertEqual(run["checksums"], {"direct": 500000500000, "function_call": 500000500000})
                        for case in ("direct", "function_call"):
                            item = run["cases"][case]
                            self.assertEqual(len(item["samples_ms"]), 50)
                            for field, value in statistics(item["samples_ms"]).items():
                                self.assertEqual(item[field], value)
                self.assertEqual(markdown(public), table_path.read_text(encoding="utf-8"))
                self.assertNotIn("C:\\", public_path.read_text(encoding="utf-8"))
                altered = copy.deepcopy(public)
                altered["runs"][0]["cases"]["direct"]["median_ms"] += 1
                with self.assertRaisesRegex(ValueError, "published statistics differ"):
                    markdown(altered)


if __name__ == "__main__":
    unittest.main()
