import json
import os
import statistics
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

    def make_archive(self, stamp: str, low: float = 0.100, high: float = 0.250,
                     count: int = 50) -> Path:
        experiment_id = f"{stamp}_function_call_numeric_sum"
        sources = []
        for language in ("c", "javascript", "python"):
            document = fixture_document(language, experiment_id)
            direct = [low] * (count // 2) + [high] * (count - count // 2)
            call = [0.400] * count
            document["config"]["measurement_iterations"] = count
            for case, samples in (("direct", direct), ("function_call", call)):
                document["results"][case].update(samples_ms=samples, min_ms=min(samples), max_ms=max(samples),
                                                  mean_ms=sum(samples) / count,
                                                  median_ms=statistics.median(samples))
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

    def test_default_text_matches_legacy_output_exactly(self) -> None:
        path = self.make_archive("20260801_130000")
        index = json.loads((path / "archive.json").read_text(encoding="utf-8"))
        direct = ", ".join(f"{i}:{'0.1' if i <= 25 else '0.25'}" for i in range(1, 51))
        call = ", ".join(f"{i}:0.4" for i in range(1, 51))
        expected = (
            "検証済み履歴のサンプル。入力順、単位 ms。中央値は samples_ms から再計算。\n"
            f"履歴 1: {path} (experiment_id={index['experiment_id']}, "
            f"archive_id={index['archive_id']}, archived_at={index['archived_at']})\n"
            "  c/direct: 中央値 0.175, 最小 0.1, 最大 0.25, 前半 0.1, 後半 0.25\n"
            f"    samples_ms (1-50): {direct}\n"
            "  c/function_call: 中央値 0.4, 最小 0.4, 最大 0.4, 前半 0.4, 後半 0.4\n"
            f"    samples_ms (1-50): {call}\n"
            "Cの各サンプルは0.001 ms単位で保存。丸め幅程度の差を原因として解釈しないでください。\n"
        )
        result = self.run_cli(path)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, result.stdout)

    def test_summary_counts_statistics_identity_and_input_preservation(self) -> None:
        for count in (50, 51):
            with self.subTest(count=count):
                path = self.make_archive(f"202608{count - 49:02d}_130000", count=count)
                before = {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}
                plain = self.run_cli(path)
                result = self.run_cli(path, extra=("--summary-only",))
                self.assertEqual(0, result.returncode, result.stderr)
                expected_lines = [line.replace(": 中央値", f": 件数 {count}, 中央値", 1)
                                  for line in plain.stdout.splitlines()
                                  if not line.startswith("    samples_ms")]
                self.assertEqual("\n".join(expected_lines) + "\n", result.stdout)
                median = "0.175" if count == 50 else "0.25"
                self.assertIn(f"c/direct: 件数 {count}, 中央値 {median}, 最小 0.1, "
                              "最大 0.25, 前半 0.1, 後半 0.25", result.stdout)
                self.assertNotIn("samples_ms (", result.stdout)
                self.assertNotRegex(result.stdout, r"\b\d+:0\.")
                self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()})

    def test_summary_multiple_archives_all_languages_and_order(self) -> None:
        first = self.make_archive("20260801_130000")
        second = self.make_archive("20260802_130000", low=0.200, high=0.300)
        result = self.run_cli(second, first, extra=("--summary-only", "--all-languages"))
        self.assertEqual(0, result.returncode, result.stderr)
        lines = result.stdout.splitlines()
        headers = [line for line in lines if line.startswith("履歴 ")]
        self.assertTrue(headers[0].startswith(f"履歴 1: {second} "))
        self.assertTrue(headers[1].startswith(f"履歴 2: {first} "))
        rows = [line.strip().split(":", 1)[0] for line in lines if line.startswith("  ")]
        self.assertEqual(["c/direct", "c/function_call", "javascript/direct",
                          "javascript/function_call", "python/direct", "python/function_call"] * 2, rows)
        self.assertEqual(12, result.stdout.count("件数 50"))
        self.assertNotIn("samples_ms (", result.stdout)
        self.assertNotRegex(result.stdout, r"\b\d+:0\.")

    def test_summary_json_conflict_precedes_input_loading(self) -> None:
        missing = self.root / "missing"
        for flags in (("--summary-only", "--json"), ("--json", "--summary-only")):
            with self.subTest(flags=flags):
                result = self.run_cli(missing, extra=flags)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("--summary-only is text-only and cannot be combined with --json", result.stderr)

    def test_summary_errors_match_default_and_do_not_modify_inputs(self) -> None:
        path = self.make_archive("20260801_130000")
        (path / "c.json").write_bytes(b"{}")
        other = self.make_archive("20260802_130000")
        (other / "experiment.json").unlink()
        valid = self.make_archive("20260803_130000")
        for paths in ((path,), (other,), (valid, valid)):
            with self.subTest(paths=paths):
                before = {str(p): p.read_bytes() for folder in paths for p in folder.iterdir() if p.is_file()}
                plain = self.run_cli(*paths)
                result = self.run_cli(*paths, extra=("--summary-only",))
                self.assertEqual(2, result.returncode)
                self.assertEqual((plain.stdout, plain.stderr), (result.stdout, result.stderr))
                self.assertEqual("", result.stdout)
                self.assertEqual(before, {str(p): p.read_bytes() for folder in paths
                                          for p in folder.iterdir() if p.is_file()})


if __name__ == "__main__":
    unittest.main()
