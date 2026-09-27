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


def balanced_fixture():
    document = fixture()
    document["measurement_settings"]["pair_run_order"] = "balanced ABBA rounds"
    first, second, third, fourth = document["runs"]
    document["runs"] = [first, second, fourth, third]
    for index, run in enumerate(document["runs"], start=1):
        run["run_number"] = index
        run["started_at"] = f"2026-09-27T09:00:{index:02d}+09:00"
        run["execution_order"] = "A_then_B" if run["cycle"] == 1 else "B_then_A"
        run["scheduled_order"] = (["cpu_a", "cpu_b"] if run["cycle"] == 1 else ["cpu_b", "cpu_a"])
        run["position"] = 1 if index % 2 else 2
    return document


def comparison_fixture(a_first_a, a_first_b, b_first_a, b_first_b):
    document = balanced_fixture()
    values = {(1, "A"): a_first_a, (1, "B"): a_first_b,
              (2, "A"): b_first_a, (2, "B"): b_first_b}
    for run in document["runs"]:
        run["median_ms"] = values[(run["cycle"], run["comparison_cpu"])]
    return document


class CpuPairAnalysisTests(unittest.TestCase):
    def test_pure_cpu_difference_has_no_aggregate_position_difference(self):
        result = analyze(comparison_fixture(10, 12, 10, 12))
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertEqual(2, result["aggregate_pair_statistics"]["median_b_minus_a_ms"])
        self.assertEqual(0, result["position_effect"]["median_second_minus_first_ms"])
        self.assertFalse(result["order_effect"]["comparison_reversal"])
        self.assertEqual("same_direction", result["order_effect"]["comparison_direction"])
        self.assertEqual("unchanged", result["order_effect"]["magnitude_change"])
        self.assertEqual(10, result["order_statistics"]["B_then_A"]["cpu_a_statistics"]["median_of_run_medians_ms"])

    def test_first_position_faster_reverses_apparent_cpu_winner(self):
        result = analyze(comparison_fixture(10, 12, 12, 10))
        self.assertEqual(2, result["position_effect"]["median_second_minus_first_ms"])
        self.assertEqual(10, result["position_statistics"]["first"]["median_of_run_medians_ms"])
        self.assertEqual(12, result["position_statistics"]["second"]["median_of_run_medians_ms"])
        self.assertEqual(2, result["order_statistics"]["A_then_B"]["median_b_minus_a_ms"])
        self.assertEqual(-2, result["order_statistics"]["B_then_A"]["median_b_minus_a_ms"])
        self.assertTrue(result["order_effect"]["comparison_reversal"])
        self.assertEqual("reversed", result["order_effect"]["comparison_direction"])

    def test_second_position_faster_has_negative_effect(self):
        result = analyze(comparison_fixture(12, 10, 10, 12))
        self.assertEqual(-2, result["position_effect"]["median_second_minus_first_ms"])
        self.assertTrue(result["order_effect"]["comparison_reversal"])
        self.assertEqual("reversed", result["order_effect"]["comparison_direction"])

    def test_order_changes_magnitude_while_cpu_direction_remains(self):
        expanded = analyze(comparison_fixture(10, 11, 10, 12))
        self.assertEqual(1, expanded["order_statistics"]["A_then_B"]["median_b_minus_a_ms"])
        self.assertEqual(2, expanded["order_statistics"]["B_then_A"]["median_b_minus_a_ms"])
        self.assertEqual(1, expanded["order_effect"]["b_first_minus_a_first_b_minus_a_ms"])
        self.assertEqual("expanded", expanded["order_effect"]["magnitude_change"])
        self.assertFalse(expanded["order_effect"]["comparison_reversal"])
        contracted = analyze(comparison_fixture(10, 12, 10, 11))
        self.assertEqual("contracted", contracted["order_effect"]["magnitude_change"])

    def test_order_reversal_reports_observation_only(self):
        result = analyze(comparison_fixture(10, 11, 11, 10))
        self.assertTrue(result["order_effect"]["comparison_reversal"])
        self.assertEqual(-2, result["order_effect"]["b_first_minus_a_first_b_minus_a_ms"])
        self.assertTrue(all("caused" not in text for text in result["interpretation_limitations"]))

    def test_tie_is_not_a_reversal(self):
        result = analyze(comparison_fixture(10, 10, 10, 12))
        self.assertFalse(result["order_effect"]["comparison_reversal"])
        self.assertEqual("tie_in_one_order", result["order_effect"]["comparison_direction"])

    def test_single_order_and_legacy_data_report_insufficient_data(self):
        result = analyze(fixture())
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertEqual(2, result["order_statistics"]["A_then_B"]["complete_pair_count"])
        self.assertEqual(0, result["order_statistics"]["B_then_A"]["complete_pair_count"])
        self.assertEqual("insufficient_data", result["order_effect"]["status"])
        self.assertIsNone(result["order_effect"]["comparison_reversal"])
        self.assertIsNone(result["order_effect"]["comparison_direction"])
        self.assertEqual("insufficient_data", result["position_effect"]["status"])
        self.assertIsNone(result["position_effect"]["median_second_minus_first_ms"])

    def test_missing_explicit_order_and_position_recover_from_balanced_plan(self):
        document = balanced_fixture()
        for run in document["runs"]:
            del run["execution_order"]
            del run["position"]
        result = analyze(document)
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertEqual(["A_then_B", "B_then_A"], [pair["execution_order"] for pair in result["cycle_pairs"]])
        self.assertEqual("available", result["position_effect"]["status"])

    def test_incomplete_reverse_order_is_not_used_for_effects(self):
        document = balanced_fixture()
        document["runs"][2]["status"] = "pending"
        result = analyze(document)
        self.assertFalse(result["analysis_valid"])
        self.assertEqual(0, result["order_statistics"]["B_then_A"]["complete_pair_count"])
        self.assertEqual(1, result["position_effect"]["complete_pair_count"])
        self.assertIsNone(result["order_effect"]["comparison_direction"])

    def test_legacy_position_can_be_inferred_from_saved_order(self):
        document = fixture()
        for run in document["runs"]:
            del run["position"]
        result = analyze(document)
        self.assertTrue(result["analysis_valid"], result["validation_errors"])
        self.assertEqual(15.0, result["position_statistics"]["first"]["median_of_run_medians_ms"])
        self.assertEqual("insufficient_data", result["position_effect"]["status"])

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

    def test_balanced_round_save_load_and_analysis_preserve_candidate_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runs.json"
            path.write_text(json.dumps(balanced_fixture()), encoding="utf-8")
            loaded = load_runs(path)
            self.assertEqual([(run["cycle"], run["execution_order"], run["comparison_cpu"], run["position"])
                              for run in loaded["runs"]],
                             [(1, "A_then_B", "A", 1), (1, "A_then_B", "B", 2),
                              (2, "B_then_A", "B", 1), (2, "B_then_A", "A", 2)])
            result = analyze(loaded)
            self.assertTrue(result["analysis_valid"], result["validation_errors"])
            self.assertEqual({"A_then_B": 1, "B_then_A": 1}, result["round_order_counts"])
            self.assertEqual(["A_then_B", "B_then_A"], [pair["execution_order"] for pair in result["cycle_pairs"]])
            self.assertEqual([2.0, -2.0], [pair["b_minus_a_ms"] for pair in result["cycle_pairs"]])
            self.assertFalse(any("always measured before" in s for s in result["interpretation_limitations"]))

    def test_balanced_round_rejects_swapped_identity_order_and_position(self):
        for field, value in (("comparison_cpu", "A"), ("position", 2),
                             ("execution_order", "A_then_B"), ("scheduled_order", ["cpu_a", "cpu_b"])):
            with self.subTest(field=field):
                document = balanced_fixture()
                document["runs"][2][field] = value
                self.assertFalse(analyze(document)["analysis_valid"])

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

    def test_all_candidate_types_accept_matching_topology(self):
        for candidate, core_b, class_b in (
            ("same_core_siblings", 0, 1),
            ("same_efficiency_class_different_core", 1, 1),
            ("different_efficiency_class", 1, 2),
        ):
            with self.subTest(candidate=candidate):
                doc = fixture()
                doc["comparison"]["candidate_type"] = candidate
                doc["comparison"]["cpu_b"]["physical_core_id"] = core_b
                doc["comparison"]["cpu_b"]["efficiency_class"] = class_b
                result = analyze(doc)
                self.assertTrue(result["analysis_valid"], result["validation_errors"])

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
