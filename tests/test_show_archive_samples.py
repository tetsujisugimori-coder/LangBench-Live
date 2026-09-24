import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_compare_archives import fixture_document
from tests.test_show_archive_metrics import ShowArchiveMetricsTests
from tools.archive_results import archive_results


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tools" / "show_archive_samples.py"


class ShowArchiveSamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def make_archive(self, stamp: str, low: float = 0.100, high: float = 0.250) -> Path:
        experiment_id = f"{stamp}_function_call_numeric_sum"
        sources = []
        for language in ("c", "javascript", "python"):
            document = fixture_document(language, experiment_id)
            direct = [low] * 25 + [high] * 25
            call = [0.400] * 50
            document["config"]["measurement_iterations"] = 50
            for case, samples in (("direct", direct), ("function_call", call)):
                document["results"][case].update(samples_ms=samples, min_ms=min(samples), max_ms=max(samples),
                                                  mean_ms=sum(samples) / 50,
                                                  median_ms=(min(samples) + max(samples)) / 2)
            document["timing"].update(measurement_ms=sum(direct) + sum(call),
                                      benchmark_total_ms=sum(direct) + sum(call) +
                                      document["timing"]["setup_ms"] + document["timing"]["warmup_ms"])
            source = self.root / f"{stamp}_{language}.json"
            source.write_text(json.dumps(document) + "\n", encoding="utf-8")
            sources.append(source)
        definition = {"schema_version": "1.0", "benchmark": "function_call_numeric_sum",
                      "languages": ["c", "javascript", "python"],
                      "config": document["config"], "expected_checksum": 3}
        manifest = self.root / f"{stamp}_experiment.json"
        manifest.write_text(json.dumps(definition), encoding="utf-8")
        return archive_results(sources, experiment_id, self.root / "history", manifest)

    def run_cli(self, *paths: Path, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(COMMAND), *extra, *(str(path) for path in paths)],
                              capture_output=True, text=True, encoding="utf-8", check=False,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})

    def test_ordered_fifty_samples_and_half_medians(self) -> None:
        path = self.make_archive("20260801_130000")
        before = [(path / name).read_bytes() for name in ("archive.json", "experiment.json", "c.json")]
        completed = self.run_cli(path, extra=("--json",))
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(path.name, report["runs"][0]["archive_id"])
        self.assertEqual(2, len(report["runs"][0]["cases"]))
        row = report["runs"][0]["cases"][0]
        self.assertEqual([0.100] * 25 + [0.250] * 25, row["samples_ms"])
        self.assertEqual((0.175, 0.100, 0.250, 0.100, 0.250),
                         tuple(row[key] for key in ("median_ms", "min_ms", "max_ms",
                                                    "first_half_median_ms", "second_half_median_ms")))
        self.assertEqual(before, [(path / name).read_bytes() for name in ("archive.json", "experiment.json", "c.json")])
        plain = self.run_cli(path)
        self.assertEqual(0, plain.returncode, plain.stderr)
        self.assertIn("1:0.1", plain.stdout)
        self.assertIn("26:0.25", plain.stdout)
        self.assertIn("50:0.25", plain.stdout)

    def test_all_languages_and_distinct_archives_keep_input_order(self) -> None:
        first = self.make_archive("20260801_130000")
        second = self.make_archive("20260802_130000", low=0.200, high=0.300)
        completed = self.run_cli(second, first, extra=("--json", "--all-languages"))
        self.assertEqual(0, completed.returncode, completed.stderr)
        runs = json.loads(completed.stdout)["runs"]
        self.assertEqual([str(second), str(first)], [run["path"] for run in runs])
        self.assertEqual(6, len(runs[0]["cases"]))
        self.assertEqual({"c", "javascript", "python"}, {row["language"] for row in runs[0]["cases"]})
        self.assertEqual([0.250, 0.175], [run["cases"][0]["median_ms"] for run in runs])

    def test_tampered_and_missing_files_have_no_measurement_output(self) -> None:
        altered = self.make_archive("20260801_130000")
        (altered / "c.json").write_bytes(b"{}")
        result = self.run_cli(altered, extra=("--json",))
        self.assertEqual(2, result.returncode)
        self.assertEqual("SHA256_MISMATCH", json.loads(result.stdout)["error"]["code"])
        self.assertEqual({"error"}, set(json.loads(result.stdout)))
        missing = self.make_archive("20260802_130000")
        (missing / "experiment.json").unlink()
        result = self.run_cli(missing, extra=("--json",))
        self.assertEqual(2, result.returncode)
        self.assertEqual("MISSING_FILE", json.loads(result.stdout)["error"]["code"])

    def test_same_archive_is_not_a_distinct_run(self) -> None:
        path = self.make_archive("20260801_130000")
        result = self.run_cli(path, path, extra=("--json",))
        self.assertEqual(2, result.returncode)
        self.assertEqual("DUPLICATE_ARCHIVE", json.loads(result.stdout)["error"]["code"])

    def test_rehashed_definition_mismatch_is_rejected(self) -> None:
        path = self.make_archive("20260801_130000")
        ShowArchiveMetricsTests.rewrite(path, "experiment.json",
                                        lambda document: document["config"].update(warmup_iterations=4))
        result = self.run_cli(path, extra=("--json",))
        self.assertEqual(2, result.returncode)
        self.assertEqual("RESULT_DEFINITION_MISMATCH", json.loads(result.stdout)["error"]["code"])


if __name__ == "__main__":
    unittest.main()
