import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_show_archive_metrics import ShowArchiveMetricsTests


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tools" / "show_archive_variability.py"


class ShowArchiveVariabilityTests(unittest.TestCase):
    make_archive = ShowArchiveMetricsTests.make_archive
    rewrite = staticmethod(ShowArchiveMetricsTests.rewrite)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_cli(self, *paths: Path, json_mode: bool = True) -> subprocess.CompletedProcess:
        command = [sys.executable, str(COMMAND)]
        if json_mode:
            command.append("--json")
        return subprocess.run([*command, *(str(path) for path in paths)], capture_output=True, text=True,
                              encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                                     "PYTHONDONTWRITEBYTECODE": "1"}, check=False)

    def three_archives(self) -> list[Path]:
        return [self.make_archive(f"2026080{day}_130000") for day in (1, 2, 3)]

    def test_comparable_all_pairs_and_sample_derived_range(self) -> None:
        paths = self.three_archives()
        for path, samples in zip(paths[1:], ([2.0, 4.0], [3.0, 5.0])):
            def change(document):
                document["results"]["direct"].update(samples_ms=samples, min_ms=min(samples),
                                                       max_ms=max(samples), mean_ms=sum(samples) / 2,
                                                       median_ms=sum(samples) / 2)
                document["timing"].update(measurement_ms=sum(samples) + 3,
                                          benchmark_total_ms=sum(samples) + 5)
            self.rewrite(path, "python.json", change)
        self.rewrite(paths[2], "python.json", lambda d: d["results"]["direct"].update(median_ms=4.0005))
        before = [(path / "python.json").read_bytes() for path in paths]
        completed = self.run_cli(*paths)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual("ms", report["unit"])
        self.assertEqual("comparable", report["verdict"])
        self.assertEqual({"comparable": 3, "caution": 0, "incomparable": 0}, report["pairwise"]["counts"])
        self.assertEqual([(0, 1), (0, 2), (1, 2)],
                         [(p["left_index"], p["right_index"]) for p in report["pairwise"]["pairs"]])
        self.assertEqual([1.5, 3.0, 4.0], [next(m["median_ms"] for m in run["medians"]
                                          if m["language"] == "python" and m["case"] == "direct")
                                          for run in report["runs"]])
        row = next(c for c in report["aggregate"]["cases"]
                   if c["language"] == "python" and c["case"] == "direct")
        self.assertEqual((1.5, 4.0, 2.5), (row["min_median_ms"], row["max_median_ms"], row["range_ms"]))
        self.assertEqual("comparable", report["aggregate"]["status"])
        self.assertEqual(6, len(report["aggregate"]["cases"]))
        self.assertEqual(before, [(path / "python.json").read_bytes() for path in paths])
        self.assertNotIn("NaN", completed.stdout)
        self.assertNotIn("Infinity", completed.stdout)
        plain = self.run_cli(*paths, json_mode=False)
        self.assertIn("python/direct: 最小 1.5 ms, 最大 4 ms, 差 2.5 ms", plain.stdout)
        self.assertIn("archived_at=", plain.stdout)

    def test_caution_marks_aggregate_as_reference_and_lists_reasons_per_pair(self) -> None:
        paths = self.three_archives()
        self.rewrite(paths[0], "c.json", lambda d: d["environment"].update(os_version=None))
        report = json.loads(self.run_cli(*paths).stdout)
        self.assertEqual("caution", report["verdict"])
        self.assertEqual({"comparable": 1, "caution": 2, "incomparable": 0}, report["pairwise"]["counts"])
        self.assertEqual("reference", report["aggregate"]["status"])
        self.assertEqual([(0, 1), (0, 2)], [(p["left_index"], p["right_index"])
                                             for p in report["pairwise"]["pairs"] if p["verdict"] == "caution"])
        reasons = report["pairwise"]["pairs"][0]["reasons"]
        self.assertIn(("INFORMATION_MISSING", "environment.os_version"),
                      [(r["code"], r["field"]) for r in reasons])
        plain = self.run_cli(*paths, json_mode=False).stdout
        self.assertIn("参考値", plain)
        self.assertIn("[INFORMATION_MISSING] environment.os_version", plain)

    def test_incomparable_omits_group_aggregate(self) -> None:
        paths = self.three_archives()
        self.rewrite(paths[2], "experiment.json", lambda d: d["config"].update(warmup_iterations=2))
        for language in ("c", "javascript", "python"):
            self.rewrite(paths[2], f"{language}.json", lambda d: d["config"].update(warmup_iterations=2))
        report = json.loads(self.run_cli(*paths).stdout)
        self.assertEqual("incomparable", report["verdict"])
        self.assertEqual({"comparable": 1, "caution": 0, "incomparable": 2}, report["pairwise"]["counts"])
        self.assertNotIn("aggregate", report)
        self.assertEqual(3, len(report["runs"]))
        self.assertEqual("CONDITION_DIFFERENT", report["pairwise"]["pairs"][1]["reasons"][0]["code"])
        plain = self.run_cli(*paths, json_mode=False).stdout
        self.assertIn("集団の最小・最大・差は表示しません", plain)
        self.assertNotIn("最小 1.5 ms", plain)

    def test_modified_archive_is_validation_error(self) -> None:
        paths = self.three_archives()
        (paths[1] / "python.json").write_bytes(b"{}")
        completed = self.run_cli(*paths)
        self.assertEqual(2, completed.returncode)
        self.assertEqual({"error": {"code": "SHA256_MISMATCH",
                                     "message": f"SHA-256 mismatch: {paths[1] / 'python.json'}"}},
                         json.loads(completed.stdout))

    def test_input_order_changes_run_and_pair_indices_but_not_range(self) -> None:
        paths = self.three_archives()
        forward = json.loads(self.run_cli(*paths).stdout)
        reverse = json.loads(self.run_cli(*reversed(paths)).stdout)
        self.assertEqual([str(p) for p in paths], [r["path"] for r in forward["runs"]])
        self.assertEqual([str(p) for p in reversed(paths)], [r["path"] for r in reverse["runs"]])
        self.assertEqual(forward["aggregate"], reverse["aggregate"])
        self.assertEqual((0, 1), (reverse["pairwise"]["pairs"][0]["left_index"],
                                  reverse["pairwise"]["pairs"][0]["right_index"]))

    def test_same_archive_twice_is_not_two_independent_runs(self) -> None:
        path = self.make_archive("20260801_130000")
        completed = self.run_cli(path, path)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("DUPLICATE_ARCHIVE", json.loads(completed.stdout)["error"]["code"])

    def test_text_output_supports_windows_default_encoding(self) -> None:
        paths = self.three_archives()[:2]
        completed = subprocess.run([sys.executable, str(COMMAND), *(str(path) for path in paths)],
                                   capture_output=True, text=True, encoding="cp932",
                                   env={**os.environ, "PYTHONIOENCODING": "cp932",
                                        "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("履歴 1-2: comparable", completed.stdout)


if __name__ == "__main__":
    unittest.main()
