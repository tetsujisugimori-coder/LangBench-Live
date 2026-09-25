import json
import os
import unittest
from unittest.mock import patch

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
