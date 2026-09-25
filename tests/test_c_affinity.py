import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from diagnose_c_affinity import (ExperimentInvalidError, allowed_cpu_mask, build_plan,
                                 check_cpus, conditions, summarize, summarize_positions, verify_binary)


def history_snapshot(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    return {str(file.relative_to(path)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in path.rglob("*") if file.is_file()}


class AffinityPureTests(unittest.TestCase):
    def test_three_cycle_rotation_and_precommitted_unique_ids(self):
        plan = build_plan(3, 2, 5, "20260924_190000")
        expected = [
            ("normal", None), ("affinity", 2), ("affinity", 5),
            ("affinity", 2), ("affinity", 5), ("normal", None),
            ("affinity", 5), ("normal", None), ("affinity", 2),
        ]
        self.assertEqual([(run["condition"], run["logical_cpu"]) for run in plan], expected)
        self.assertEqual([(run["cycle"], run["position"]) for run in plan],
                         [(cycle, position) for cycle in (1, 2, 3) for position in (1, 2, 3)])
        self.assertEqual([run["scheduled_order"] for run in plan[3:6]], [["cpu:2", "cpu:5", "normal"]] * 3)
        for condition in conditions(2, 5):
            positions = [run["position"] for run in plan if (run["condition"], run["logical_cpu"]) == condition]
            self.assertEqual(sorted(positions), [1, 2, 3])
        ids = [run["run_id"] for run in plan]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "20260924_190000_c_function_call_numeric_sum_run_001")
        self.assertEqual(ids[-1], "20260924_190000_c_function_call_numeric_sum_run_009")
        self.assertTrue(all(run["status"] == "pending" and run["started_at"] is None for run in plan))

    def test_forty_cycle_positions_differ_by_at_most_one(self):
        plan = build_plan(40, 2, 5, "20260924_190000")
        self.assertEqual(len(plan), 120)
        self.assertEqual(len({run["run_id"] for run in plan}), 120)
        self.assertEqual({run["experiment_id"] for run in plan}, {"20260924_190000_function_call_numeric_sum"})
        self.assertEqual([run["run_number"] for run in plan], list(range(1, 121)))
        self.assertEqual([run["scheduled_order"] for run in plan[:9:3]],
                         [["normal", "cpu:2", "cpu:5"], ["cpu:2", "cpu:5", "normal"],
                          ["cpu:5", "normal", "cpu:2"]])
        self.assertTrue(all(run["status"] == "pending" for run in plan))
        for condition in conditions(2, 5):
            counts = [sum((run["condition"], run["logical_cpu"]) == condition and run["position"] == position
                          for run in plan) for position in (1, 2, 3)]
            self.assertEqual(sum(counts), 40)
            self.assertLessEqual(max(counts) - min(counts), 1)

    def test_normal_and_two_distinct_cpus(self):
        self.assertEqual(conditions(2, 5), [("normal", None), ("affinity", 2), ("affinity", 5)])
        check_cpus(2, 5, (1 << 2) | (1 << 5))

    def test_invalid_cpu_is_rejected(self):
        for a, b, mask in [(-1, 1, 3), (0, 0, 3), (0, 2, 3), (0, 64, 3)]:
            with self.subTest(a=a, b=b, mask=mask), self.assertRaises(ValueError):
                check_cpus(a, b, mask)

    def test_summary_uses_run_medians_and_counts_samples(self):
        runs = [
            {"status": "success", "condition": "normal", "logical_cpu": None, "position": 1,
             "median_ms": 0.1, "samples_ms": [0.1] * 50, "samples_ge_0_2_ms": 0},
            {"status": "success", "condition": "normal", "logical_cpu": None, "position": 2,
             "median_ms": 0.3, "samples_ms": [0.3] * 50, "samples_ge_0_2_ms": 50},
            {"status": "failed", "condition": "normal", "logical_cpu": None, "position": 3,
             "median_ms": None, "samples_ms": None, "samples_ge_0_2_ms": None},
            {"status": "success", "condition": "affinity", "logical_cpu": 2, "position": 1,
             "median_ms": 0.2, "samples_ms": [0.2] * 50, "samples_ge_0_2_ms": 50},
        ]
        normal, cpu_a, cpu_b = summarize(runs, conditions(2, 5))
        self.assertEqual((normal["run_count"], normal["median_of_medians_ms"], normal["min_median_ms"], normal["max_median_ms"]), (2, 0.2, 0.1, 0.3))
        self.assertEqual((normal["samples_ge_0_2_ms"], normal["runs_with_sample_ge_0_2_ms"]), (50, 1))
        self.assertEqual((normal["planned_runs"], normal["successful_runs"], normal["failed_runs"],
                          normal["measurement_samples"]), (3, 2, 1, 100))
        self.assertAlmostEqual(normal["mean_median_ms"], 0.2)
        self.assertAlmostEqual(normal["stddev_median_ms"], 0.1)
        self.assertEqual((cpu_a["run_count"], cpu_a["samples_ge_0_2_ms"]), (1, 50))
        self.assertEqual((cpu_b["run_count"], cpu_b["median_of_medians_ms"]), (0, None))
        positions = summarize_positions(runs, conditions(2, 5))
        self.assertEqual([row["position"] for row in positions], [1, 2, 3])
        self.assertEqual((positions[0]["conditions"][0]["successful_runs"],
                          positions[0]["conditions"][0]["median_of_medians_ms"]), (1, 0.1))
        self.assertEqual((positions[1]["conditions"][0]["samples_ge_0_2_ms"],
                          positions[2]["conditions"][0]["failed_runs"]), (50, 1))

    def test_changed_binary_is_fatal(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "benchmark.exe"
            binary.write_bytes(b"original")
            expected = hashlib.sha256(binary.read_bytes()).hexdigest()
            verify_binary(binary, expected)
            binary.write_bytes(b"changed")
            with self.assertRaisesRegex(ExperimentInvalidError, "binary SHA-256 changed"):
                verify_binary(binary, expected)


@unittest.skipUnless(sys.platform == "win32", "Windows affinity integration")
class AffinityWindowsTests(unittest.TestCase):
    def test_three_conditions_use_one_binary_and_preserve_normal_result(self):
        cpus = [cpu for cpu in range(64) if allowed_cpu_mask() & (1 << cpu)]
        if len(cpus) < 2:
            self.skipTest("fewer than two allowed logical CPUs")
        normal_path = ROOT / "results/function_call_numeric_sum_c_result.json"
        history_path = ROOT / "results/history"
        before = hashlib.sha256(normal_path.read_bytes()).hexdigest() if normal_path.exists() else None
        history_before = history_snapshot(history_path)
        with tempfile.TemporaryDirectory(prefix="langbench-affinity-test-", ignore_cleanup_errors=True) as temporary:
            output = Path(temporary) / "diagnostic"
            command = [sys.executable, "-B", str(ROOT / "tools/diagnose_c_affinity.py"), "--runs", "1", "--cpu-a", str(cpus[0]), "--cpu-b", str(cpus[1]), "--output", str(output)]
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            record = json.loads((output / "runs.json").read_text(encoding="utf-8"))
            saved_plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            stamp = record["experiment_id"].removesuffix("_function_call_numeric_sum")
            expected_runs = build_plan(1, cpus[0], cpus[1], stamp)
            plan_fields = ("experiment_id", "run_number", "number", "cycle", "position", "scheduled_order",
                           "condition", "logical_cpu", "run_id", "status")
            expected_plan = {"experiment_id": record["experiment_id"],
                             "runs": [{field: run[field] for field in plan_fields} for run in expected_runs]}
            self.assertEqual(len(record["runs"]), 3)
            self.assertEqual(len(saved_plan["runs"]), 3)
            self.assertTrue(all(run["status"] == "pending" for run in saved_plan["runs"]))
            self.assertEqual(saved_plan, expected_plan)
            self.assertEqual({run["experiment_id"] for run in saved_plan["runs"]}, {record["experiment_id"]})
            self.assertEqual([run["logical_cpu"] for run in record["runs"]], [None, cpus[0], cpus[1]])
            self.assertEqual(len({run["run_id"] for run in record["runs"]}), 3)
            self.assertEqual([row["run_count"] for row in record["summary"]], [1, 1, 1])
            self.assertEqual(summary["planned_runs"], 3)
            self.assertEqual([row["successful_runs"] for row in summary["conditions"]], [1, 1, 1])
            self.assertEqual([[row["successful_runs"] for row in position["conditions"]]
                              for position in summary["positions"]], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
            binary_hash = hashlib.sha256((output / "c-benchmark.exe").read_bytes()).hexdigest()
            self.assertEqual(record["binary_sha256"], binary_hash)
            for run in record["runs"]:
                self.assertEqual(run["status"], "success")
                self.assertEqual(run["binary_sha256"], binary_hash)
                self.assertEqual(len(run["samples_ms"]), 50)
                document = json.loads((output / run["result_file"]).read_text(encoding="utf-8"))
                self.assertEqual(run["samples_ms"], document["results"]["direct"]["samples_ms"])
                self.assertEqual(run["run_id"], document["run_id"])
                self.assertEqual(run["experiment_id"], record["experiment_id"])
                affinity_args = [arg for arg in document["execution"]["argv"] if arg.startswith("--diagnostic-affinity=")]
                self.assertEqual(affinity_args, [] if run["logical_cpu"] is None else [f"--diagnostic-affinity={run['logical_cpu']}"])
            normal = json.loads((output / record["runs"][0]["result_file"]).read_text(encoding="utf-8"))
            invalid_path = output / "invalid-cpu.json"
            arguments = [arg for arg in normal["execution"]["argv"][1:] if not arg.startswith("--result-path=")]
            arguments += [f"--result-path={invalid_path}", "--diagnostic-affinity=999"]
            invalid = subprocess.run([str(output / "c-benchmark.exe"), *arguments], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("invalid logical CPU number", invalid.stderr)
            self.assertFalse(invalid_path.exists())
        after = hashlib.sha256(normal_path.read_bytes()).hexdigest() if normal_path.exists() else None
        self.assertEqual(before, after)
        self.assertEqual(history_before, history_snapshot(history_path))


if __name__ == "__main__":
    unittest.main()
