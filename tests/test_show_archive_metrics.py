import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_compare_archives import fixture_document
from tools.archive_results import archive_results


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tools" / "show_archive_metrics.py"


class ShowArchiveMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def make_archive(self, stamp: str) -> Path:
        experiment_id = f"{stamp}_function_call_numeric_sum"
        sources = []
        for language in ("c", "javascript", "python"):
            path = self.root / f"{stamp}_{language}.json"
            path.write_text(json.dumps(fixture_document(language, experiment_id)) + "\n", encoding="utf-8")
            sources.append(path)
        definition = {"schema_version": "1.0", "benchmark": "function_call_numeric_sum",
                      "languages": ["c", "javascript", "python"],
                      "config": fixture_document("python", experiment_id)["config"],
                      "expected_checksum": 3}
        manifest = self.root / f"{stamp}_definition.json"
        manifest.write_text(json.dumps(definition), encoding="utf-8")
        return archive_results(sources, experiment_id, self.root / "history", manifest)

    @staticmethod
    def rewrite(folder: Path, name: str, mutate) -> None:
        path = folder / name
        document = json.loads(path.read_text(encoding="utf-8"))
        mutate(document)
        raw = (json.dumps(document, ensure_ascii=False) + "\n").encode()
        path.write_bytes(raw)
        index_path = folder / "archive.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if name == "experiment.json":
            index["experiment_manifest"]["sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            for entry in index["results"]:
                if entry["file"] == name:
                    entry["sha256"] = hashlib.sha256(raw).hexdigest()
        index_path.write_text(json.dumps(index), encoding="utf-8")

    def run_cli(self, left: Path, right: Path, json_mode: bool = True) -> subprocess.CompletedProcess:
        command = [sys.executable, str(COMMAND)]
        if json_mode:
            command.append("--json")
        return subprocess.run([*command, str(left), str(right)], capture_output=True, text=True,
                              encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                                     "PYTHONDONTWRITEBYTECODE": "1"}, check=False)

    def test_comparable_uses_validated_saved_medians_and_signed_differences(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")

        def change_python_direct(document):
            result = document["results"]["direct"]
            result.update(samples_ms=[2.0, 4.0], min_ms=2.0, max_ms=4.0,
                          mean_ms=3.0, median_ms=3.0)
            document["timing"].update(measurement_ms=9.0, benchmark_total_ms=11.0)

        self.rewrite(right, "python.json", change_python_direct)
        completed = self.run_cli(left, right)
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual("1.0", report["schema_version"])
        self.assertEqual("comparable", report["verdict"])
        self.assertEqual([], report["reasons"])
        self.assertEqual(left.name, report["left"]["archive_id"])
        self.assertEqual(right.parent.name, report["right"]["experiment_id"])
        self.assertEqual(6, len(report["measurements"]))
        rows = {(row["language"], row["case"]): row for row in report["measurements"]}
        self.assertEqual({("c", "direct"), ("c", "function_call"),
                          ("javascript", "direct"), ("javascript", "function_call"),
                          ("python", "direct"), ("python", "function_call")}, set(rows))
        self.assertEqual((1.5, 3.0, 1.5, 100.0, "left"),
                         tuple(rows[("python", "direct")][key] for key in
                               ("left_median_ms", "right_median_ms", "delta_ms", "change_percent", "faster")))
        self.assertEqual(0.0, rows[("c", "direct")]["delta_ms"])
        self.assertEqual("equal", rows[("c", "direct")]["faster"])
        text = self.run_cli(left, right, json_mode=False)
        self.assertEqual(0, text.returncode, text.stderr)
        self.assertIn("差(ms) = 右中央値 − 左中央値", text.stdout)
        self.assertIn("python/direct: 左 1.5 ms, 右 3 ms, 差 +1.5 ms, 変化率 +100%, 左が速い", text.stdout)

    def test_caution_keeps_reason_beside_reference_numbers(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "c.json", lambda d: d["environment"].update(os_version=None))
        completed = self.run_cli(left, right)
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual("caution", report["verdict"])
        self.assertIn({"code": "INFORMATION_MISSING", "field": "environment.os_version",
                       "message": "c の environment.os_version が片方または両方で記録されていません。",
                       "language": "c"}, report["reasons"])
        self.assertIn("delta_ms", report["measurements"][0])
        self.assertIn("change_percent", report["measurements"][0])
        text = self.run_cli(left, right, json_mode=False)
        self.assertIn("参考値", text.stdout)
        self.assertIn("[INFORMATION_MISSING] environment.os_version", text.stdout)
        self.assertIn("差 +0 ms, 変化率 +0%", text.stdout)

    def test_incomparable_omits_all_derived_numbers_and_speed_order(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "experiment.json", lambda d: d["config"].update(warmup_iterations=2))
        for language in ("c", "javascript", "python"):
            self.rewrite(right, f"{language}.json", lambda d: d["config"].update(warmup_iterations=2))
        def change_python_direct(document):
            document["results"]["direct"].update(samples_ms=[2.0, 4.0], min_ms=2.0,
                                                   max_ms=4.0, mean_ms=3.0, median_ms=3.0)
            document["timing"].update(measurement_ms=9.0, benchmark_total_ms=11.0)
        self.rewrite(right, "python.json", change_python_direct)
        completed = self.run_cli(left, right)
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual("incomparable", report["verdict"])
        self.assertEqual(["CONDITION_DIFFERENT"], [item["code"] for item in report["reasons"]])
        for row in report["measurements"]:
            self.assertEqual({"language", "case", "left_median_ms", "right_median_ms"}, set(row))
        self.assertEqual(3.0, next(row["right_median_ms"] for row in report["measurements"]
                                   if row["language"] == "python" and row["case"] == "direct"))
        text = self.run_cli(left, right, json_mode=False)
        self.assertIn("[CONDITION_DIFFERENT] config", text.stdout)
        self.assertIn("差・変化率・速度の優劣は表示しません", text.stdout)
        self.assertNotIn("差 +", text.stdout)
        self.assertNotIn("が速い", text.stdout)

    def test_modified_archive_is_validation_error_without_measurements(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        (right / "python.json").write_bytes(b"{}")
        completed = self.run_cli(left, right)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("SHA256_MISMATCH", json.loads(completed.stdout)["error"]["code"])
        self.assertNotIn("measurements", json.loads(completed.stdout))
        self.assertNotIn("verdict", json.loads(completed.stdout))
        text = self.run_cli(left, right, json_mode=False)
        self.assertEqual(2, text.returncode)
        self.assertEqual("", text.stdout)
        self.assertIn("検証エラー [SHA256_MISMATCH]", text.stderr)

    def test_zero_left_median_has_explicit_null_percent(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")

        def zero_direct(document):
            document["results"]["direct"].update(samples_ms=[0.0, 0.0], min_ms=0.0,
                                                    max_ms=0.0, mean_ms=0.0, median_ms=0.0)
            document["timing"].update(measurement_ms=3.0, benchmark_total_ms=5.0)

        self.rewrite(left, "python.json", zero_direct)
        completed = self.run_cli(left, right)
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        row = next(row for row in report["measurements"] if row["language"] == "python" and row["case"] == "direct")
        self.assertEqual(1.5, row["delta_ms"])
        self.assertIsNone(row["change_percent"])
        self.assertEqual("LEFT_MEDIAN_ZERO", row["change_percent_unavailable_reason"])
        self.assertNotIn("Infinity", completed.stdout)
        self.assertNotIn("NaN", completed.stdout)
        text = self.run_cli(left, right, json_mode=False)
        self.assertIn("変化率 計算不能 (左中央値が0)", text.stdout)

    def test_rehashed_inconsistent_median_is_validation_error(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "python.json", lambda d: d["results"]["direct"].update(median_ms=4.0))
        completed = self.run_cli(left, right)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("RESULT_VALIDATION_FAILED", json.loads(completed.stdout)["error"]["code"])

    def test_negative_difference_marks_right_as_faster(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")

        def faster_direct(document):
            document["results"]["direct"].update(samples_ms=[0.5, 1.0], min_ms=0.5,
                                                    max_ms=1.0, mean_ms=0.75, median_ms=0.75)
            document["timing"].update(measurement_ms=4.5, benchmark_total_ms=6.5)

        self.rewrite(right, "python.json", faster_direct)
        report = json.loads(self.run_cli(left, right).stdout)
        row = next(row for row in report["measurements"] if row["language"] == "python" and row["case"] == "direct")
        self.assertEqual((-0.75, -50.0, "right"),
                         (row["delta_ms"], row["change_percent"], row["faster"]))

    def test_uses_saved_median_within_validator_tolerance_without_early_rounding(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "python.json", lambda d: d["results"]["direct"].update(median_ms=1.5005))
        completed = self.run_cli(left, right)
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        row = next(row for row in report["measurements"] if row["language"] == "python" and row["case"] == "direct")
        self.assertEqual(1.5005, row["right_median_ms"])
        self.assertAlmostEqual(0.0005, row["delta_ms"])
        self.assertAlmostEqual((1.5005 - 1.5) / 1.5 * 100, row["change_percent"])


if __name__ == "__main__":
    unittest.main()
