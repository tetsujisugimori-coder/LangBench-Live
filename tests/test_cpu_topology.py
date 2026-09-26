import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.function_call_numeric_sum.python import main as function_call_main
from benchmarks.jit_object_numeric_sum.python import main as jit_object_main
from tools import cpu_topology


class CpuTopologyTests(unittest.TestCase):
    @staticmethod
    def analysis_fixture(process_affinity=True):
        return {
            "status": "available",
            "logical_cpu_count": 6,
            "physical_core_count": 4,
            "processor_group_count": 2,
            "processor_groups": [],
            "process_affinity": (
                {"allowed_logical_cpu_count": 3,
                 "allowed_logical_cpu_ids": [
                     {"group_id": 0, "processor_number": n} for n in range(3)
                 ]} if process_affinity else None
            ),
            "cores": [
                {"core_id": 0, "logical_processors": [
                    {"group_id": 0, "processor_number": 0},
                    {"group_id": 0, "processor_number": 1},
                ], "efficiency_class": 8},
                {"core_id": 1, "logical_processors": [
                    {"group_id": 0, "processor_number": 2},
                    {"group_id": 0, "processor_number": 3},
                ], "efficiency_class": 8},
                {"core_id": 2, "logical_processors": [
                    {"group_id": 0, "processor_number": 4},
                ], "efficiency_class": 2},
                # Repeated core_id confirms processor groups are part of core identity.
                {"core_id": 0, "logical_processors": [
                    {"group_id": 1, "processor_number": 0},
                ], "efficiency_class": 2},
            ],
        }

    def test_analysis_reports_smt_siblings_single_thread_core_and_class_counts(self):
        result = cpu_topology.analyze_topology(
            self.analysis_fixture(), [0, 1, 2, 4, {"group_id": 1, "processor_number": 0}]
        )
        by_cpu = {(item["logical_cpu"]["group_id"], item["logical_cpu"]["processor_number"]): item
                  for item in result["logical_cpu_analysis"]}
        self.assertEqual(0, by_cpu[(0, 0)]["core_id"])
        self.assertEqual([{"group_id": 0, "processor_number": 1}], by_cpu[(0, 0)]["sibling_logical_cpus"])
        self.assertEqual(1, by_cpu[(0, 0)]["sibling_logical_cpu_count"])
        self.assertEqual(2, by_cpu[(0, 0)]["logical_thread_count"])
        self.assertEqual(1, by_cpu[(0, 4)]["logical_thread_count"])
        summary = result["topology_summary"]
        self.assertEqual(6, summary["logical_cpu_count"])
        self.assertEqual(4, summary["physical_core_count"])
        self.assertEqual(2, summary["processor_group_count"])
        self.assertEqual(3, summary["process_affinity_logical_cpu_count"])
        self.assertEqual({1: 2, 2: 2}, summary["physical_cores_by_logical_thread_count"])
        self.assertEqual({2: 2, 8: 2}, summary["efficiency_class_physical_core_counts"])
        self.assertEqual({2: 2, 8: 4}, summary["efficiency_class_logical_cpu_counts"])
        comparisons = result["comparisons"]
        self.assertTrue(comparisons[0]["same_physical_core"])
        self.assertTrue(comparisons[0]["same_efficiency_class"])
        self.assertFalse(comparisons[1]["same_physical_core"])
        self.assertTrue(comparisons[1]["same_efficiency_class"])
        different_class = next(
            pair for pair in comparisons
            if pair["first_logical_cpu"] == {"group_id": 0, "processor_number": 0}
            and pair["second_logical_cpu"] == {"group_id": 0, "processor_number": 4}
        )
        self.assertFalse(different_class["same_efficiency_class"])
        self.assertFalse(comparisons[-1]["same_processor_group"])
        self.assertFalse(comparisons[-1]["same_physical_core"])

    def test_cpu_identity_includes_processor_group(self):
        result = cpu_topology.analyze_topology(
            self.analysis_fixture(), [{"group_id": 0, "processor_number": 0},
                                      {"group_id": 1, "processor_number": 0}]
        )
        self.assertEqual(0, result["logical_cpu_analysis"][0]["logical_cpu"]["group_id"])
        self.assertEqual(1, result["logical_cpu_analysis"][1]["logical_cpu"]["group_id"])
        self.assertFalse(result["comparisons"][0]["same_processor_group"])

    def test_none_affinity_and_missing_efficiency_class_are_nonfatal(self):
        topology = self.analysis_fixture(process_affinity=False)
        topology["cores"][0].pop("efficiency_class")
        result = cpu_topology.analyze_topology(topology, [0, 2])
        self.assertIsNone(result["topology_summary"]["process_affinity_logical_cpu_count"])
        self.assertIsNone(result["logical_cpu_analysis"][0]["efficiency_class"])
        self.assertIsNone(result["comparisons"][0]["same_efficiency_class"])

    def test_unavailable_and_unsupported_topologies_are_distinct_from_bad_input(self):
        for status in ("unavailable", "unsupported"):
            with self.subTest(status=status), self.assertRaises(cpu_topology.TopologyUnavailableError):
                cpu_topology.analyze_topology({"status": status, "error": "not collected", "cores": []})

    def test_empty_cores_and_invalid_cpu_requests(self):
        empty = cpu_topology.analyze_topology({"status": "available", "cores": [], "process_affinity": None})
        self.assertEqual(0, empty["topology_summary"]["physical_core_count"])
        with self.assertRaisesRegex(ValueError, "does not exist"):
            cpu_topology.analyze_topology(self.analysis_fixture(), [99])
        with self.assertRaisesRegex(ValueError, "processor group 3 does not exist"):
            cpu_topology.analyze_topology(self.analysis_fixture(), [{"group_id": 3, "processor_number": 0}])

    def test_malformed_core_records_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing core_id"):
            cpu_topology.analyze_topology({"status": "available", "cores": [{"logical_processors": []}]})

    def test_non_windows_is_explicitly_unsupported_and_serializable(self):
        with patch.object(cpu_topology.platform, "system", return_value="Linux"):
            result = cpu_topology.collect_topology()
        self.assertEqual("unsupported", result["status"])
        self.assertIsNone(result["physical_core_count"])
        self.assertIsNone(result["processor_group_count"])
        self.assertGreaterEqual(result["logical_cpu_count"], 1)
        self.assertEqual(result, json.loads(json.dumps(result)))

    def test_windows_api_failure_is_recorded_and_does_not_raise(self):
        with patch.object(cpu_topology.platform, "system", return_value="Windows"), patch.object(
            cpu_topology, "_windows_topology", side_effect=OSError("diagnostic denied")
        ):
            result = cpu_topology.collect_topology()
        self.assertEqual("unavailable", result["status"])
        self.assertIn("diagnostic denied", result["error"])
        self.assertIsNone(result["process_affinity"])

    def test_safe_collector_returns_success_result_unchanged(self):
        topology = {"status": "available", "logical_cpu_count": 1}
        with patch.object(cpu_topology, "collect_topology", return_value=topology):
            self.assertIs(topology, cpu_topology.safe_collect_topology())

    def test_safe_collector_records_unexpected_exception(self):
        with patch.object(cpu_topology, "collect_topology", side_effect=RuntimeError("unexpected topology failure")), patch.object(
            cpu_topology.os, "cpu_count", return_value=7
        ):
            result = cpu_topology.safe_collect_topology()
        self.assertEqual("unavailable", result["status"])
        self.assertEqual("RuntimeError: unexpected topology failure", result["error"])
        self.assertEqual(7, result["logical_cpu_count"])
        self.assertIsNone(result["physical_core_count"])
        self.assertIsNone(result["processor_group_count"])
        self.assertEqual([], result["processor_groups"])
        self.assertIsNone(result["process_affinity"])
        self.assertEqual([], result["cores"])

    def test_benchmark_metadata_survives_unexpected_topology_exception(self):
        with patch.object(cpu_topology, "collect_topology", side_effect=RuntimeError("diagnostic only")):
            function_call_result = function_call_main.metadata(
                "success", "20260926_010000_function_call_numeric_sum",
                "20260926_010001_python_function_call_numeric_sum",
            )
            jit_object_result = jit_object_main.build_metadata(
                Path.cwd(), "success", "20260926_010000_jit_object_numeric_sum",
                "20260926_010001_python_jit_object_numeric_sum",
            )
        for result in (function_call_result, jit_object_result):
            self.assertEqual("success", result["status"])
            self.assertEqual("unavailable", result["environment"]["cpu_topology"]["status"])
            self.assertIn("diagnostic only", result["environment"]["cpu_topology"]["error"])

    @unittest.skipUnless(os.name == "nt", "Windows topology API integration")
    def test_windows_topology_has_consistent_group_and_core_identifiers(self):
        result = cpu_topology.collect_topology()
        self.assertEqual("available", result["status"], result.get("error"))
        self.assertGreaterEqual(result["logical_cpu_count"], 1)
        self.assertGreaterEqual(result["physical_core_count"], 1)
        self.assertGreaterEqual(result["processor_group_count"], 1)
        self.assertEqual(result["processor_group_count"], len(result["processor_groups"]))
        group_ids = {group["group_id"] for group in result["processor_groups"]}
        processors = [processor for group in result["processor_groups"] for processor in group["logical_processors"]]
        processor_ids = [(item["group_id"], item["processor_number"]) for item in processors]
        self.assertEqual(len(processor_ids), len(set(processor_ids)))
        self.assertEqual(result["logical_cpu_count"], len(processor_ids))
        self.assertEqual(group_ids, {item["group_id"] for item in processors})
        for core in result["cores"]:
            for processor in core["logical_processors"]:
                self.assertIn((processor["group_id"], processor["processor_number"]), processor_ids)


if __name__ == "__main__":
    unittest.main()
