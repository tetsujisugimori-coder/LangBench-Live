import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_cpu_pair import InputError, analyze, load_runs, main


def fixture():
    settings = {"benchmark_identifier": "function_call_numeric_sum", "language": "C", "case": "C/direct",
                "item_count": 100, "warmup_iterations": 2, "measurement_iterations": 4,
                "measurement_order": ["direct", "function_call"], "runs_per_cpu": 2,
                "pair_run_order": "CPU A then CPU B, repeated", "compiler_options": ["-O2"]}
    runs = []
    for cycle, a, b in ((1, 10.0, 12.0), (2, 20.0, 18.0)):
        for position, label, value, processor in ((1, "A", a, 0), (2, "B", b, 1)):
            runs.append({"experiment_id": "experiment-1", "cycle": cycle, "position": position, "scheduled_order": ["cpu_a", "cpu_b"],
                         "comparison_cpu": label, "logical_cpu": processor, "processor_group_id": 0,
                         "status": "success", "median_ms": value, "binary_sha256": "abc",
                         "benchmark": "C/direct", "benchmark_config": {"item_count": 100, "warmup_iterations": 2,
                         "measurement_iterations": 4}, "run_id": f"r{cycle}{label}"})
    return {"schema_version": "1.0", "benchmark": "function_call_numeric_sum", "case": "C/direct",
            "experiment_id": "experiment-1", "binary_sha256": "abc", "compiler_options": ["-O2"],
            "measurement_settings": settings, "comparison": {"candidate_type": "same_core_siblings",
            "selection_reason": "fixture pair", "topology_sha256": "topology-hash",
            "cpu_a": {"group_id": 0, "processor_number": 0, "physical_core_id": 0, "efficiency_class": 1},
            "cpu_b": {"group_id": 0, "processor_number": 1, "physical_core_id": 0, "efficiency_class": 1}},
            "runs": runs}


class CpuPairAnalysisTests(unittest.TestCase):
    def test_valid_pair_statistics_and_metadata(self):
        result = analyze(fixture(), "runs.json", "2026-09-27T00:00:00+09:00")
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertEqual("same_core_siblings", result["comparison"]["candidate_type"])
        self.assertEqual(2, result["cpu_a_statistics"]["successful_run_count"])
        self.assertEqual(15.0, result["cpu_a_statistics"]["mean_run_median_ms"])
        self.assertEqual(15.0, result["cpu_a_statistics"]["median_of_run_medians_ms"])
        self.assertEqual(10.0, result["cpu_a_statistics"]["minimum_run_median_ms"])
        self.assertEqual(20.0, result["cpu_a_statistics"]["maximum_run_median_ms"])
        self.assertEqual(10.0, result["cpu_a_statistics"]["range_of_run_medians_ms"])
        self.assertAlmostEqual(7.0710678118654755, result["cpu_a_statistics"]["standard_deviation_run_medians_ms"])
        self.assertEqual(2, result["aggregate_pair_statistics"]["complete_pair_count"])
        self.assertEqual([2.0, -2.0], [p["b_minus_a_ms"] for p in result["cycle_pairs"]])
        self.assertEqual([1.2, 0.9], [p["b_over_a_ratio"] for p in result["cycle_pairs"]])
        self.assertTrue(any("always measured before" in s for s in result["interpretation_limitations"]))

    def test_missing_comparison_candidate_cpu_and_malformed_json(self):
        doc = fixture()
        del doc["comparison"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        del doc["comparison"]["cpu_b"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(InputError):
                load_runs(path)

    def test_failed_pending_missing_half_hash_config_and_settings_are_invalid(self):
        for status in ("failed", "pending"):
            doc = fixture()
            doc["runs"][0]["status"] = status
            self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"].pop()
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["binary_sha256"] = "different"
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["benchmark_config"]["item_count"] = 101
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["benchmark_config"]["warmup_iterations"] = 99
        self.assertFalse(analyze(doc)["analysis_valid"])

    def test_candidate_missing_settings_mismatch_and_zero_division(self):
        doc = fixture()
        doc["comparison"]["candidate_type"] = None
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["measurement_settings"]["measurement_iterations"] = 7
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        for run in doc["runs"]:
            if run["comparison_cpu"] == "A":
                run["median_ms"] = 0
        result = analyze(doc)
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertIsNone(result["cycle_pairs"][0]["b_over_a_ratio"])
        self.assertIsNone(result["cycle_pairs"][0]["b_minus_a_percent_of_a"])
        self.assertIsNone(result["aggregate_pair_statistics"]["median_b_over_a_ratio"])

    def test_cli_writes_report_for_valid_json_and_returns_nonzero_for_invalid_experiment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runs.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            self.assertEqual(0, main([str(path)]))
            output = path.with_name("cpu-pair-analysis.json")
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["analysis_valid"])
            self.assertEqual(2, main([str(path), "--output", str(path)]))
            self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["runs"])
            doc = fixture()
            doc["runs"][0]["status"] = "pending"
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(1, main([str(path)]))


if __name__ == "__main__":
    unittest.main()
