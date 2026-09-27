import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.test_cpu_pair_analysis import balanced_fixture
from tools.analyze_cpu_pair import analyze, render_summary
from tools.cpu_pair_time import _busy_observation, load_diagnostics


ORIGIN = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)


def time_fixture(values=None):
    document = balanced_fixture()
    template = deepcopy(document["runs"])
    document["runs"] = []
    document["started_at"] = ORIGIN.isoformat()
    document["ended_at"] = (ORIGIN + timedelta(seconds=100)).isoformat()
    diagnostics = {}
    values = values or {"A": [10, 10, 10, 10], "B": [12, 12, 12, 12]}
    for cycle in range(1, 5):
        order = ("A_then_B", "B_then_A", "B_then_A", "A_then_B")[cycle - 1]
        for position, side in enumerate(("A", "B") if order == "A_then_B" else ("B", "A"), 1):
            index = len(document["runs"])
            run = deepcopy(next(item for item in template if item["comparison_cpu"] == side))
            start = ORIGIN + timedelta(seconds=10 * (index + 1))
            qpc = 1000 * (index + 1)
            name = f"cpu-monitor-run-{index + 1:03d}.json"
            run.update(cycle=cycle, position=position, run_number=index + 1,
                       run_id=f"r{cycle}{side}", execution_order=order,
                       scheduled_order=[f"cpu_{side.lower()}" for side in (("A", "B") if order == "A_then_B" else ("B", "A"))],
                       started_at=start.isoformat(), ended_at=(start + timedelta(seconds=5)).isoformat(),
                       median_ms=values[side][cycle - 1], diagnostic_qpc={"start_qpc": qpc, "end_qpc": qpc + 500, "frequency_hz": 1000},
                       cpu_diagnostic_file=name)
            document["runs"].append(run)
            busy = 10 * (cycle - 1)
            diagnostics[name] = {"clock": "windows_qpc", "frequency_hz": 1000,
                                 "requested_interval_ms": 20,
                                 "started_qpc": qpc - 20, "ended_qpc": qpc + 530,
                                 "observations": [{"start_qpc": qpc - 10, "end_qpc": qpc, "cpu_busy_percent": 99},
                                                  {"start_qpc": qpc + 10, "end_qpc": qpc + 50, "cpu_busy_percent": busy + 10},
                                                  {"start_qpc": qpc + 50, "end_qpc": qpc + 100, "cpu_busy_percent": busy + 30},
                                                  {"start_qpc": qpc + 500, "end_qpc": qpc + 520, "cpu_busy_percent": 99}]}
    document["measurement_settings"]["runs_per_cpu"] = 4
    return document, diagnostics


class CpuPairTimeTests(unittest.TestCase):
    def test_alignment_overlap_statistics_and_balanced_identity(self):
        document, diagnostics = time_fixture()
        result = analyze(document, diagnostics=diagnostics)
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        time = result["time_analysis"]
        self.assertEqual("available", time["status"])
        self.assertEqual(8, time["runs_with_diagnostic_coverage"])
        self.assertEqual(100, time["experiment_elapsed_seconds"])
        first = time["run_sequence"][0]
        self.assertEqual((1, "r1A", "A", 1, 10, 10),
                         (first["cycle"], first["run_id"], first["comparison_cpu"], first["position"],
                          first["elapsed_since_experiment_start_seconds"], first["median_ms"]))
        self.assertEqual([1, 2], first["cpu_busy"]["sample_indices"])
        self.assertEqual({"start_qpc": 1000, "end_qpc": 1500}, first["cpu_busy"]["run_qpc_range"])
        self.assertEqual((500, 90, 0.18, 20),
                         (first["cpu_busy"]["run_duration_qpc"], first["cpu_busy"]["overlap_duration_qpc"],
                          first["cpu_busy"]["overlap_ratio"], first["cpu_busy"]["requested_interval_ms"]))
        self.assertEqual((2, 20, 20, 10, 30),
                         (first["cpu_busy"]["sample_count"], first["cpu_busy"]["median_cpu_busy_percent"],
                          first["cpu_busy"]["mean_cpu_busy_percent"], first["cpu_busy"]["minimum_cpu_busy_percent"],
                          first["cpu_busy"]["maximum_cpu_busy_percent"]))
        self.assertEqual(("B", 1, "A", 2),
                         (time["run_sequence"][2]["comparison_cpu"], time["run_sequence"][2]["position"],
                          time["run_sequence"][3]["comparison_cpu"], time["run_sequence"][3]["position"]))
        self.assertEqual([1, 2, 3, 4], [row["cycle"] for row in time["cycle_trend"]])
        self.assertEqual([10, 30, 50, 70], [row["elapsed_since_experiment_start_seconds"] for row in time["cycle_trend"]])
        self.assertEqual(10, time["cycle_trend"][0]["a_b_start_gap_seconds"])
        self.assertEqual("available", time["early_late_comparison"]["status"])

    def test_qpc_overlap_clips_run_boundaries_and_unions_samples(self):
        run = {"cpu_diagnostic_file": "monitor.json",
               "diagnostic_qpc": {"start_qpc": 100, "end_qpc": 200, "frequency_hz": 1000}}
        monitor = {"clock": "windows_qpc", "frequency_hz": 1000, "started_qpc": 40,
                   "ended_qpc": 260, "requested_interval_ms": 20, "observations": [
                       {"start_qpc": 50, "end_qpc": 150, "cpu_busy_percent": 10},
                       {"start_qpc": 175, "end_qpc": 250, "cpu_busy_percent": 20}]}
        busy = _busy_observation(run, monitor)
        self.assertEqual((100, 75, 0.75, [0, 1]),
                         (busy["run_duration_qpc"], busy["overlap_duration_qpc"],
                          busy["overlap_ratio"], busy["sample_indices"]))
        full = deepcopy(monitor)
        full["observations"] = [{"start_qpc": 90, "end_qpc": 210, "cpu_busy_percent": 20}]
        busy = _busy_observation(run, full)
        self.assertEqual((100, 1.0), (busy["overlap_duration_qpc"], busy["overlap_ratio"]))
        overlapping = deepcopy(monitor)
        overlapping["observations"] = [
            {"start_qpc": 90, "end_qpc": 160, "cpu_busy_percent": 10},
            {"start_qpc": 120, "end_qpc": 210, "cpu_busy_percent": 20},
            {"start_qpc": 130, "end_qpc": 140, "cpu_busy_percent": None}]
        busy = _busy_observation(run, overlapping)
        self.assertEqual((2, 100, 1.0),
                         (busy["sample_count"], busy["overlap_duration_qpc"], busy["overlap_ratio"]))
        self.assertLessEqual(busy["overlap_ratio"], 1.0)
        outside = deepcopy(monitor)
        outside["observations"] = [{"start_qpc": 40, "end_qpc": 100, "cpu_busy_percent": 10}]
        busy = _busy_observation(run, outside)
        self.assertEqual(("insufficient_data", "no_overlapping_valid_samples", 0, 0.0),
                         (busy["status"], busy["reason"], busy["overlap_duration_qpc"], busy["overlap_ratio"]))
        missing = _busy_observation(run, None)
        self.assertEqual("diagnostic_file_missing", missing["reason"])
        self.assertIsNone(missing["overlap_ratio"])
        self.assertEqual(100, missing["run_duration_qpc"])
        wrong_frequency = deepcopy(monitor)
        wrong_frequency["frequency_hz"] = 2000
        self.assertEqual("clock_mapping_unavailable", _busy_observation(run, wrong_frequency)["reason"])
        short_monitor = deepcopy(monitor)
        short_monitor["ended_qpc"] = 199
        self.assertEqual("clock_mapping_unavailable", _busy_observation(run, short_monitor)["reason"])

    def test_density_summary_cli_and_optional_interval(self):
        document, diagnostics = time_fixture()
        first_name = document["runs"][0]["cpu_diagnostic_file"]
        second_name = document["runs"][1]["cpu_diagnostic_file"]
        diagnostics[first_name]["observations"] = diagnostics[first_name]["observations"][:2]
        diagnostics[first_name].pop("requested_interval_ms")
        diagnostics[second_name]["observations"].insert(3, {
            "start_qpc": 2100, "end_qpc": 2150, "cpu_busy_percent": 30})
        result = analyze(document, diagnostics=diagnostics)
        density = result["time_analysis"]["diagnostic_density"]
        self.assertEqual((8, 8), (density["covered_run_count"], density["successful_run_count"]))
        self.assertEqual({"minimum": 1, "median": 2.0, "maximum": 3},
                         density["sample_count_per_covered_run"])
        self.assertEqual({"minimum": 0.08, "median": 0.18, "maximum": 0.28},
                         density["overlap_ratio_per_covered_run"])
        self.assertIsNone(result["time_analysis"]["run_sequence"][0]["cpu_busy"]["requested_interval_ms"])
        self.assertIn("samples/run median 2.0, range 1..3", render_summary(result))
        self.assertIn("QPC overlap median 0.18", render_summary(result))
        no_coverage = analyze(document, diagnostics={})
        density = no_coverage["time_analysis"]["diagnostic_density"]
        self.assertTrue(no_coverage["analysis_valid"])
        self.assertEqual(0, density["covered_run_count"])
        self.assertIsNone(density["sample_count_per_covered_run"]["median"])
        self.assertIsNone(density["overlap_ratio_per_covered_run"]["median"])
        self.assertIn("samples/run median None", render_summary(no_coverage))

    def test_synthetic_time_and_order_patterns_are_descriptive(self):
        scenarios = [
            ({"A": [10, 10, 10, 10], "B": [12, 12, 12, 12]}, 0, 0),
            ({"A": [10, 10, 15, 15], "B": [12, 12, 17, 17]}, 5, 5),
            ({"A": [10, 10, 15, 15], "B": [12, 12, 12, 12]}, 5, 0),
            ({"A": [10, 12, 14, 16], "B": [12, 14, 16, 18]}, 4, 4),
            ({"A": [10, 11, 11, 10], "B": [13, 12, 12, 13]}, 0, 0),
            ({"A": [10, 10, 15, 15], "B": [10, 10, 15, 15]}, 5, 5),
        ]
        for values, expected_a, expected_b in scenarios:
            with self.subTest(values=values):
                document, diagnostics = time_fixture(values)
                result = analyze(document, diagnostics=diagnostics)
                self.assertTrue(result["analysis_valid"], result["validation_errors"])
                comparison = result["time_analysis"]["early_late_comparison"]
                self.assertEqual(expected_a, comparison["by_cpu"]["A"]["late_minus_early_ms"])
                self.assertEqual(expected_b, comparison["by_cpu"]["B"]["late_minus_early_ms"])
                self.assertIn("order_effect", result)
                self.assertIn("position_effect", result)
                busy = [row["cpu_a_busy"]["median_cpu_busy_percent"] for row in result["time_analysis"]["cycle_trend"]]
                self.assertEqual([20, 30, 40, 50], busy)
        order_only, diagnostics = time_fixture({"A": [10, 11, 11, 10], "B": [13, 12, 12, 13]})
        result = analyze(order_only, diagnostics=diagnostics)
        self.assertEqual(-2, result["order_effect"]["b_first_minus_a_first_b_minus_a_ms"])
        self.assertEqual(0, result["time_analysis"]["early_late_comparison"]["by_cpu"]["A"]["late_minus_early_ms"])
        trend_only, diagnostics = time_fixture({"A": [10, 10, 15, 15], "B": [10, 10, 15, 15]})
        result = analyze(trend_only, diagnostics=diagnostics)
        self.assertEqual(0, result["order_effect"]["b_first_minus_a_first_b_minus_a_ms"])
        self.assertEqual(5, result["time_analysis"]["early_late_comparison"]["by_cpu"]["A"]["late_minus_early_ms"])

    def test_joint_cpu_position_elapsed_and_busy_summaries(self):
        document, diagnostics = time_fixture({"A": [10, 12, 14, 16], "B": [20, 22, 24, 26]})
        result = analyze(document, diagnostics=diagnostics)
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        joint = result["time_analysis"]["joint_analysis"]
        self.assertEqual(4, joint["complete_cycle_count"])
        self.assertEqual((2, 13), (joint["by_cpu_and_position"]["A"][1]["sample_count"],
                                   joint["by_cpu_and_position"]["A"][1]["median_ms"]))
        self.assertEqual(13, joint["by_cpu_and_position"]["A"][2]["median_ms"])
        self.assertEqual((11, 15), (joint["by_elapsed_half_and_cpu"]["early"]["A"]["median_ms"],
                                    joint["by_elapsed_half_and_cpu"]["late"]["A"]["median_ms"]))
        self.assertGreater(joint["elapsed_correlation_by_cpu"]["A"]["pearson_r"], 0.9)
        self.assertEqual(1, joint["busy_correlation_by_cpu"]["B"]["pearson_r"])
        self.assertEqual(4, joint["busy_covered_cycle_count"])
        self.assertEqual((1, 1, 2), tuple(joint["busy_bands"][name]["cycle_count"]
                                          for name in ("low", "middle", "high")))
        self.assertEqual(10, joint["busy_bands"]["low"]["by_cpu"]["A"]["median_ms"])
        self.assertEqual("insufficient_data", joint["busy_bands"]["low"]["status"])
        self.assertIn("CPU A median by position", render_summary(result))

        missing = analyze(document, diagnostics={})["time_analysis"]["joint_analysis"]
        self.assertEqual(0, missing["busy_covered_cycle_count"])
        self.assertIsNone(missing["busy_correlation_by_cpu"]["A"]["pearson_r"])

    def test_missing_invalid_and_old_data_do_not_invalidate_existing_analysis(self):
        document, diagnostics = time_fixture()
        cases = []
        cases.append(({}, "diagnostic_file_missing"))
        no_anchor = deepcopy(document)
        no_anchor["runs"][0].pop("diagnostic_qpc")
        cases.append((diagnostics, "clock_mapping_unavailable", no_anchor))
        empty = deepcopy(diagnostics)
        empty[document["runs"][0]["cpu_diagnostic_file"]]["observations"] = []
        cases.append((empty, "diagnostic_samples_missing"))
        outside = deepcopy(diagnostics)
        outside[document["runs"][0]["cpu_diagnostic_file"]]["observations"] = [
            {"start_qpc": 1, "end_qpc": 2, "cpu_busy_percent": 10}]
        cases.append((outside, "no_overlapping_valid_samples"))
        broken = deepcopy(diagnostics)
        broken[document["runs"][0]["cpu_diagnostic_file"]] = {"_load_error": "diagnostic_file_unreadable"}
        cases.append((broken, "diagnostic_file_unreadable"))
        for case in cases:
            data, reason = case[:2]
            doc = case[2] if len(case) == 3 else document
            result = analyze(doc, diagnostics=data)
            self.assertTrue(result["analysis_valid"], result["validation_errors"])
            self.assertEqual(reason, result["time_analysis"]["run_sequence"][0]["cpu_busy"]["reason"])
        malformed = deepcopy(document)
        malformed["runs"][0]["started_at"] = "bad-time"
        result = analyze(malformed, diagnostics=diagnostics)
        self.assertTrue(result["analysis_valid"])
        self.assertEqual("invalid_or_missing_timestamp", next(row for row in result["time_analysis"]["run_sequence"] if row["run_id"] == "r1A")["timing_reason"])
        old = balanced_fixture()
        result = analyze(old)
        self.assertTrue(result["analysis_valid"])
        self.assertEqual("insufficient_data", result["time_analysis"]["status"])
        for status in ("pending", "failed"):
            doc = deepcopy(document)
            doc["runs"][0]["status"] = status
            result = analyze(doc, diagnostics=diagnostics)
            self.assertFalse(result["analysis_valid"])
            self.assertEqual(7, result["time_analysis"]["successful_run_count"])
        invalid_cycle = deepcopy(document)
        invalid_cycle["runs"][0]["cycle"] = []
        result = analyze(invalid_cycle, diagnostics=diagnostics)
        self.assertFalse(result["analysis_valid"])

    def test_corrupt_json_is_reported_without_overwriting_source(self):
        document, _ = time_fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            name = document["runs"][0]["cpu_diagnostic_file"]
            (directory / name).write_text("{bad", encoding="utf-8")
            loaded = load_diagnostics(document, directory)
            self.assertEqual("diagnostic_file_unreadable", loaded[name]["_load_error"])
            self.assertTrue(analyze(document, diagnostics=loaded)["analysis_valid"])


if __name__ == "__main__":
    unittest.main()
