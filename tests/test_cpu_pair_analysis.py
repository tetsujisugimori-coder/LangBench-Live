import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_cpu_pair import InputError, analyze, load_runs, main


def fixture():
    settings = {"benchmark_identifier": "function_call_numeric_sum", "language": "C", "case": "C/direct",
                "item_count": 100, "warmup_iterations": 2, "measurement_iterations": 4,
                "measurement_order": ["direct", "function_call"], "runs_per_cpu": 2,
                "pair_run_order": "CPU A then CPU B, repeated", "compiler_options": ["-O2"],
                "affinity_is_the_only_configured_run_difference": True}
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

    def test_top_level_and_run_experiment_ids_and_binary_hashes_are_consistent(self):
        doc = fixture()
        del doc["experiment_id"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["experiment_id"] = "  "
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["experiment_id"] = "other-experiment"
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        del doc["binary_sha256"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["binary_sha256"] = "other-hash"
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["binary_sha256"] = "other-hash"
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["runs"][0]["binary_sha256"] = None
        self.assertFalse(analyze(doc)["analysis_valid"])

    def test_all_candidate_topology_relationships_accept_matching_metadata(self):
        candidates = (
            ("same_core_siblings", 0, 1),
            ("same_efficiency_class_different_core", 1, 1),
            ("different_efficiency_class", 1, 2),
        )
        for candidate, core_b, class_b in candidates:
            with self.subTest(candidate=candidate):
                doc = fixture()
                doc["comparison"]["candidate_type"] = candidate
                doc["comparison"]["cpu_b"]["physical_core_id"] = core_b
                doc["comparison"]["cpu_b"]["efficiency_class"] = class_b
                result = analyze(doc)
                self.assertTrue(result["analysis_valid"], result["validation_errors"])

    def test_candidate_type_must_match_cpu_topology(self):
        invalid_changes = [
            ("same_core_siblings", "cpu_b", "physical_core_id", 1),
            ("same_core_siblings", "cpu_b", "efficiency_class", 2),
            ("same_core_siblings", "cpu_b", "efficiency_class", 2),
            ("same_efficiency_class_different_core", "cpu_b", "physical_core_id", 0),
            ("same_efficiency_class_different_core", "cpu_b", "efficiency_class", 2),
            ("different_efficiency_class", "cpu_b", "efficiency_class", 1),
            ("different_efficiency_class", "cpu_b", "group_id", 1),
        ]
        for candidate, side, field, value in invalid_changes:
            with self.subTest(candidate=candidate, field=field, value=value):
                doc = fixture()
                doc["comparison"]["candidate_type"] = candidate
                if candidate == "same_efficiency_class_different_core":
                    doc["comparison"]["cpu_b"]["physical_core_id"] = 1
                if candidate == "different_efficiency_class":
                    doc["comparison"]["cpu_b"]["efficiency_class"] = 2
                doc["comparison"][side][field] = value
                self.assertFalse(analyze(doc)["analysis_valid"])

    def test_measurement_order_value_must_match_saved_format(self):
        doc = fixture()
        doc["measurement_settings"]["measurement_order"] = ["function_call", "direct"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        del doc["measurement_settings"]["measurement_order"]
        self.assertFalse(analyze(doc)["analysis_valid"])
        doc = fixture()
        doc["measurement_settings"]["measurement_order"] = "direct,function_call"
        self.assertFalse(analyze(doc)["analysis_valid"])

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
