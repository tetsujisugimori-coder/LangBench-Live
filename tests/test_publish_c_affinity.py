import copy
import hashlib
import json
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.diagnose_c_affinity import build_plan, conditions
from tools.publish_c_affinity import build_public, markdown, recalculate


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATH = ROOT / "artifacts/c-affinity/public-data.json"
SUMMARY_PATH = ROOT / "artifacts/c-affinity/summary.md"


class PublishCAffinityTests(unittest.TestCase):
    def test_recalculate_public_rows_with_success_failure_and_pending(self):
        values = [0.1] * 49 + [0.2]
        experiment_id = "20260924_201136_function_call_numeric_sum"
        runs = [
            {"experiment_id": experiment_id, "run_number": 1,
             "run_id": "20260924_201136_c_function_call_numeric_sum_run_001", "cycle": 1,
             "position": 1, "condition": "normal", "condition_label": "normal", "logical_cpu": None,
             "plan_status": "pending", "status": "success", "samples_ms": values,
             "median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values),
             "samples_ge_0_2_ms": 1},
            {"experiment_id": experiment_id, "run_number": 2,
             "run_id": "20260924_201136_c_function_call_numeric_sum_run_002", "cycle": 1,
             "position": 2, "condition": "normal", "condition_label": "normal", "logical_cpu": None,
             "plan_status": "pending", "status": "failed", "samples_ms": None,
             "median_ms": None, "min_ms": None, "max_ms": None, "samples_ge_0_2_ms": None},
            {"experiment_id": experiment_id, "run_number": 3,
             "run_id": "20260924_201136_c_function_call_numeric_sum_run_003", "cycle": 1,
             "position": 3, "condition": "normal", "condition_label": "normal", "logical_cpu": None,
             "plan_status": "pending", "status": "pending", "samples_ms": None,
             "median_ms": None, "min_ms": None, "max_ms": None, "samples_ge_0_2_ms": None},
        ]
        public = {"experiment_id": experiment_id, "planned_runs": 3, "conditions": [
            {"condition": "normal", "condition_label": "normal", "logical_cpu": None}], "runs": runs}
        summary = recalculate(public)
        row = summary["conditions"][0]
        self.assertEqual((row["planned_runs"], row["successful_runs"], row["failed_runs"], row["pending_runs"]),
                         (3, 1, 1, 1))
        self.assertEqual((row["measurement_samples"], row["samples_ge_0_2_ms"],
                          row["runs_with_sample_ge_0_2_ms"]), (50, 1, 1))
        self.assertEqual((row["median_of_medians_ms"], row["mean_median_ms"],
                          row["stddev_median_ms"], row["min_median_ms"], row["max_median_ms"]),
                         (0.1, 0.1, 0.0, 0.1, 0.1))
        self.assertEqual([position["conditions"][0]["planned_runs"] for position in summary["positions"]],
                         [1, 1, 1])
        invalid = copy.deepcopy(public)
        invalid["runs"][0]["median_ms"] = 0.2
        with self.assertRaisesRegex(ValueError, "statistics differ"):
            recalculate(invalid)

    def test_published_data_recalculates_without_private_paths(self):
        public = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(public["schema_version"], "1.0")
        self.assertEqual(public["planned_runs"], 120)
        self.assertEqual(public["measurement"], {
            "item_count": 1000000, "warmup_iterations": 5, "measurement_iterations": 50,
            "measurement_order": ["direct", "function_call"], "threshold_ms": 0.2,
            "compiler": "gcc", "compiler_version": "gcc (Rev5, Built by MSYS2 project) 16.1.0",
            "compiler_options": ["-O2", "-std=c11", "-Wall", "-Wextra"],
        })
        self.assertEqual(len({run["run_id"] for run in public["runs"]}), 120)
        self.assertEqual({run["experiment_id"] for run in public["runs"]}, {public["experiment_id"]})
        self.assertTrue(all(run["plan_status"] == "pending" and run["status"] == "success"
                            and len(run["samples_ms"]) == 50 for run in public["runs"]))
        self.assertEqual(len(public["binary_sha256"]), 64)
        self.assertEqual(len(public["c_source_sha256"]), 64)
        self.assertEqual(recalculate(public), public["summary"])
        self.assertEqual(markdown(public), SUMMARY_PATH.read_text(encoding="utf-8"))

        normal, cpu_a, cpu_b = public["summary"]["conditions"]
        self.assertEqual((normal["planned_runs"], normal["successful_runs"], normal["failed_runs"],
                          normal["median_of_medians_ms"], normal["mean_median_ms"], normal["stddev_median_ms"],
                          normal["min_median_ms"], normal["max_median_ms"], normal["measurement_samples"],
                          normal["samples_ge_0_2_ms"], normal["runs_with_sample_ge_0_2_ms"]),
                         (40, 40, 0, 0.104, 0.1161, 0.031933759565701, 0.096, 0.2545, 2000, 90, 6))
        self.assertEqual((cpu_a["median_of_medians_ms"], cpu_a["mean_median_ms"],
                          cpu_a["stddev_median_ms"], cpu_a["min_median_ms"], cpu_a["max_median_ms"],
                          cpu_a["samples_ge_0_2_ms"], cpu_a["runs_with_sample_ge_0_2_ms"]),
                         (0.13475, 0.1354375, 0.026172549431608686, 0.101, 0.203, 159, 12))
        self.assertEqual((cpu_b["median_of_medians_ms"], cpu_b["mean_median_ms"],
                          cpu_b["stddev_median_ms"], cpu_b["min_median_ms"], cpu_b["max_median_ms"],
                          cpu_b["samples_ge_0_2_ms"], cpu_b["runs_with_sample_ge_0_2_ms"]),
                         (0.11725, 0.12763750000000001, 0.022882031023272388, 0.101, 0.182, 187, 20))
        self.assertEqual([[row["planned_runs"] for row in position["conditions"]]
                          for position in public["summary"]["positions"]],
                         [[14, 13, 13], [13, 14, 13], [13, 13, 14]])
        expected_position_values = [
            [(0.1035, 0.10639285714285714, 0.006959522180408068, 0.096, 0.1255, 700, 4, 1),
             (0.139, 0.13607692307692307, 0.0291764170797147, 0.101, 0.203, 650, 45, 4),
             (0.116, 0.12584615384615386, 0.019825570721617822, 0.108, 0.182, 650, 63, 6)],
            [(0.104, 0.11942307692307692, 0.03514357702222641, 0.096, 0.229, 650, 36, 2),
             (0.13875, 0.14260714285714285, 0.02230004690211962, 0.111, 0.181, 700, 69, 4),
             (0.1215, 0.1281923076923077, 0.024717277094822732, 0.101, 0.182, 650, 53, 7)],
            [(0.1055, 0.12323076923076923, 0.04107479827405654, 0.096, 0.2545, 650, 50, 3),
             (0.1195, 0.1270769230769231, 0.02439723041804143, 0.102, 0.1805, 650, 45, 4),
             (0.11725, 0.12878571428571428, 0.023645230782876923, 0.105, 0.171, 700, 71, 7)],
        ]
        for position, expected_rows in zip(public["summary"]["positions"], expected_position_values):
            for row, expected in zip(position["conditions"], expected_rows):
                actual = (row["median_of_medians_ms"], row["mean_median_ms"], row["stddev_median_ms"],
                          row["min_median_ms"], row["max_median_ms"], row["measurement_samples"],
                          row["samples_ge_0_2_ms"], row["runs_with_sample_ge_0_2_ms"])
                for actual_value, expected_value in zip(actual[:5], expected[:5]):
                    self.assertAlmostEqual(actual_value, expected_value, places=14)
                self.assertEqual(actual[5:], expected[5:])
        content = PUBLIC_PATH.read_text(encoding="utf-8")
        self.assertNotIn("C:\\", content)
        self.assertNotIn("tetsu", content)
        self.assertNotIn("compile_command", content)
        self.assertNotIn("c-benchmark.exe", content)
        for source in (public["source_files"]["plan"], public["source_files"]["runs"],
                       public["source_files"]["optimization_analysis"]):
            self.assertEqual(len(source["sha256"]), 64)
        for run in public["runs"]:
            self.assertEqual(len(run["source_result"]["sha256"]), 64)
            self.assertEqual(run["source_result"]["file"], f"run-{run['run_number']:03d}.json")
        with tempfile.TemporaryDirectory() as temporary:
            generated_summary = Path(temporary) / "summary.md"
            process = subprocess.run([sys.executable, "-B", str(ROOT / "tools/publish_c_affinity.py"),
                                      "--recalculate-public", str(PUBLIC_PATH),
                                      "--table-output", str(generated_summary)],
                                     cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual(generated_summary.read_text(encoding="utf-8"), SUMMARY_PATH.read_text(encoding="utf-8"))

    def test_builder_emits_path_free_failed_run_data_and_raw_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            stamp = "20260924_201136"
            experiment_id = f"{stamp}_function_call_numeric_sum"
            planned = build_plan(1, 0, 1, stamp)
            (folder / "plan.json").write_text(json.dumps({"experiment_id": experiment_id,
                "runs": [{key: row[key] for key in ("experiment_id", "run_number", "number", "cycle",
                         "position", "scheduled_order", "condition", "logical_cpu", "run_id", "status")}
                         for row in planned]}), encoding="utf-8")
            binary = b"fixed-binary"
            (folder / "c-benchmark.exe").write_bytes(binary)
            (folder / "optimization-analysis.json").write_text("{}", encoding="utf-8")
            config = {"item_count": 1000000, "warmup_iterations": 5, "measurement_iterations": 50}
            runs = []
            for row in planned:
                runs.append({**row, "started_at": "start", "ended_at": "end", "status": "failed",
                             "result_file": f"run-{row['number']:03d}.json",
                             "binary_sha256": hashlib.sha256(binary).hexdigest(),
                             "benchmark": "C/direct", "benchmark_config": config,
                             "samples_ms": None, "median_ms": None, "min_ms": None, "max_ms": None,
                             "samples_ge_0_2_ms": None, "error": "fixture failure"})
            (folder / "runs.json").write_text(json.dumps({
                "schema_version": "1.0", "benchmark": "function_call_numeric_sum", "case": "C/direct",
                "experiment_id": experiment_id,
                "conditions": [{"condition": mode, "logical_cpu": cpu} for mode, cpu in conditions(0, 1)],
                "runs_per_condition": 1,
                "binary_sha256": hashlib.sha256(binary).hexdigest(),
                "c_source_sha256": hashlib.sha256((ROOT / "benchmarks/function_call_numeric_sum/c/main.c").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "compiler": "gcc test", "compiler_options": ["-O2", "-std=c11", "-Wall", "-Wextra"],
                "environment": {"os": "Windows", "os_version": "test", "logical_processors": 2,
                                "cpu_model": "test CPU"}, "runs": runs,
            }), encoding="utf-8")
            public = build_public(folder)
            self.assertEqual(public["planned_runs"], 3)
            self.assertEqual([row["failed_runs"] for row in public["summary"]["conditions"]], [1, 1, 1])
            self.assertEqual(public["source_files"]["plan"]["sha256"], hashlib.sha256((folder / "plan.json").read_bytes()).hexdigest())
            self.assertNotIn(str(folder), json.dumps(public))


if __name__ == "__main__":
    unittest.main()
