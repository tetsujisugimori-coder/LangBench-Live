import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.function_call_numeric_sum.python import main as function_call_main
from benchmarks.jit_object_numeric_sum.python import main as jit_object_main
from tools import cpu_topology


class CpuTopologyTests(unittest.TestCase):
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
