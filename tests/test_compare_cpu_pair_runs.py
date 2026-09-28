import json
import tempfile
import unittest
from pathlib import Path

from tools.compare_cpu_pair_runs import compare
from test_cpu_pair_analysis import balanced_fixture


class IndependentComparisonTests(unittest.TestCase):
    def test_two_experiments_keep_separate_elapsed_axes(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for number, values in ((1, (10, 11)), (2, (11, 10))):
                directory = Path(temp) / str(number)
                directory.mkdir()
                document = balanced_fixture()
                document["experiment_id"] = f"experiment-{number}"
                document["c_source_sha256"] = "same-source"
                document["started_at"] = f"2026-09-27T09:00:00+09:00"
                document["ended_at"] = f"2026-09-27T09:00:10+09:00"
                for run in document["runs"]:
                    run["experiment_id"] = document["experiment_id"]
                    run["run_id"] = f"exp{number}-{run['run_id']}"
                    run["ended_at"] = "2026-09-27T09:00:09+09:00"
                    if run["comparison_cpu"] == "B":
                        run["median_ms"] = values[run["cycle"] - 1]
                (directory / "runs.json").write_text(json.dumps(document), encoding="utf-8")
                paths.append(directory)
            result = compare(paths)
            self.assertEqual(2, len(result["experiments"]))
            self.assertEqual(["experiment-1", "experiment-2"],
                             [item["experiment_id"] for item in result["experiments"]])
            self.assertGreater(result["experiments"][0]["elapsed_correlation"]["B"]["pearson_r"], 0)
            self.assertLess(result["experiments"][1]["elapsed_correlation"]["B"]["pearson_r"], 0)
            self.assertEqual({"A_then_B": 1, "B_then_A": 1}, result["experiments"][0]["order_counts"])
            self.assertEqual(2, result["experiments"][0]["cycles"])
            self.assertEqual(1, result["experiments"][0]["cpu_position"]["B"][1]["sample_count"])
            self.assertEqual(1, result["experiments"][0]["cpu_position"]["B"][2]["sample_count"])
            self.assertEqual(0, result["experiments"][0]["busy_coverage"]["covered_runs"])
            self.assertIsNone(result["experiments"][0]["busy_by_elapsed_half"]["early"]["B"]["median_percent"])
            with self.assertRaisesRegex(ValueError, "unique"):
                compare([paths[0], paths[0]])
            changed = json.loads((paths[1] / "runs.json").read_text(encoding="utf-8"))
            changed["measurement_settings"]["item_count"] = 101
            (paths[1] / "runs.json").write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid experiment|settings differ"):
                compare(paths)

    def test_grouped_runs_keep_ids_cycles_and_effects_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for number, b_values in ((1, (10, 11)), (2, (11, 10))):
                directory = Path(temp) / f"run-{number:03d}"
                directory.mkdir()
                document = balanced_fixture()
                document["experiment_id"] = f"independent-{number}"
                document["c_source_sha256"] = "same-source"
                document["repeat_experiment_id"] = "repeat-one"
                document["started_at"] = "2026-09-27T09:00:00+09:00"
                document["ended_at"] = "2026-09-27T09:00:10+09:00"
                for run in document["runs"]:
                    run["experiment_id"] = document["experiment_id"]
                    run["run_id"] = f"independent-{number}-{run['run_id']}"
                    run["ended_at"] = "2026-09-27T09:00:09+09:00"
                    if run["comparison_cpu"] == "B":
                        run["median_ms"] = b_values[run["cycle"] - 1]
                (directory / "runs.json").write_text(json.dumps(document), encoding="utf-8")
                paths.append(directory)
            result = compare(paths, require_same_repeat_id=True)
            self.assertEqual("repeat-one", result["repeat_experiment_id"])
            self.assertEqual(["positive", "negative"],
                             [row["sign"] for row in result["cross_run"]["B"]["elapsed_correlation"]["by_run"]])
            self.assertFalse(result["cross_run"]["B"]["elapsed_correlation"]["all_available_signs_match"])
            self.assertEqual(2, result["cross_run"]["B"]["elapsed_correlation"]["range"])
            self.assertEqual([1, 1], [row["cpu_position"]["B"][1]["sample_count"]
                                      for row in result["experiments"]])
            changed = json.loads((paths[1] / "runs.json").read_text(encoding="utf-8"))
            changed["repeat_experiment_id"] = "repeat-two"
            (paths[1] / "runs.json").write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "repeat_experiment_id"):
                compare(paths, require_same_repeat_id=True)


if __name__ == "__main__":
    unittest.main()
