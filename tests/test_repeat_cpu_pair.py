import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.repeat_cpu_pair import repeat
from test_cpu_pair_analysis import balanced_fixture


class RepeatCpuPairTests(unittest.TestCase):
    def test_separate_runs_preserve_raw_data_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repeats"

            def fake_run(command, **_):
                directory = Path(command[command.index("--output") + 1])
                directory.mkdir()
                number = int(directory.name[-3:])
                document = balanced_fixture()
                document["experiment_id"] = f"independent-{number}"
                document["c_source_sha256"] = "same-source"
                document["repeat_experiment_id"] = command[command.index("--repeat-experiment-id") + 1]
                document["started_at"] = "2026-09-27T09:00:00+09:00"
                document["ended_at"] = "2026-09-27T09:00:10+09:00"
                for run in document["runs"]:
                    run["experiment_id"] = document["experiment_id"]
                    run["run_id"] = f"independent-{number}-{run['run_id']}"
                    run["ended_at"] = "2026-09-27T09:00:09+09:00"
                (directory / "runs.json").write_text(json.dumps(document), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with patch("tools.repeat_cpu_pair.subprocess.run", side_effect=fake_run):
                self.assertEqual(0, repeat(output, 2, 2, "same_core_siblings", "fixed-repeat-id"))
            first = (output / "run-001" / "runs.json").read_bytes()
            second = (output / "run-002" / "runs.json").read_bytes()
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            comparison = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(["independent-1", "independent-2"],
                             [row["experiment_id"] for row in manifest["runs"]])
            self.assertEqual(manifest["repeat_experiment_id"], comparison["repeat_experiment_id"])
            self.assertEqual("fixed-repeat-id", manifest["repeat_experiment_id"])
            self.assertNotEqual(first, second)
            self.assertEqual(first, (output / "run-001" / "runs.json").read_bytes())
            with self.assertRaises(FileExistsError):
                repeat(output, 2, 2, "same_core_siblings")

    def test_failed_first_run_keeps_manifest_without_reusing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repeats"
            failure = subprocess.CompletedProcess([], 2, "", "compiler failed")
            with patch("tools.repeat_cpu_pair.subprocess.run", return_value=failure) as runner:
                self.assertEqual(1, repeat(output, 2, 2, "same_core_siblings"))
            self.assertEqual(1, runner.call_count)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("failed", manifest["runs"][0]["status"])
            self.assertEqual("compiler failed", (output / "run-001.log").read_text(encoding="utf-8"))
            self.assertFalse((output / "run-002").exists())

    def test_success_without_runs_json_marks_failed_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repeats"
            def successful_child(command, **_):
                (output / "run-001").mkdir()
                return subprocess.CompletedProcess(command, 0, "measurement finished", "")

            with patch("tools.repeat_cpu_pair.subprocess.run", side_effect=successful_child) as runner:
                with self.assertRaises(FileNotFoundError):
                    repeat(output, 3, 2, "same_core_siblings")
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            row = manifest["runs"][0]
            self.assertEqual("failed", row["status"])
            self.assertEqual(0, row["exit_code"])
            self.assertIn("FileNotFoundError", row["error"])
            self.assertEqual(1, len(manifest["runs"]))
            self.assertEqual(1, runner.call_count)
            self.assertEqual("measurement finished", (output / "run-001.log").read_text(encoding="utf-8"))

    def test_success_with_invalid_runs_json_marks_failed_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repeats"
            def malformed_child(command, **_):
                directory = output / "run-001"
                directory.mkdir()
                (directory / "runs.json").write_text("{broken", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "measurement finished", "")

            with patch("tools.repeat_cpu_pair.subprocess.run", side_effect=malformed_child) as runner:
                with self.assertRaises(json.JSONDecodeError):
                    repeat(output, 3, 2, "same_core_siblings")
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            row = manifest["runs"][0]
            self.assertEqual("failed", row["status"])
            self.assertEqual(0, row["exit_code"])
            self.assertIn("JSONDecodeError", row["error"])
            self.assertEqual(1, len(manifest["runs"]))
            self.assertEqual(1, runner.call_count)


if __name__ == "__main__":
    unittest.main()
