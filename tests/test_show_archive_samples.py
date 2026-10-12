import hashlib
import json
import os
import shutil
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

    def file_hashes(self, *paths: Path) -> dict:
        return {str(file): hashlib.sha256(file.read_bytes()).hexdigest()
                for path in paths for file in path.iterdir() if file.is_file()}

    def test_single_sample_all_modes_statistics_and_input_hashes(self) -> None:
        path = self.make_archive("20260801_130000", count=1)
        before = self.file_hashes(path)
        for flags in (("--json",), ("--json", "--all-languages")):
            result = self.run_cli(path, extra=flags)
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual("1.0", report["schema_version"])
            rows = report["runs"][0]["cases"]
            self.assertEqual(6 if "--all-languages" in flags else 2, len(rows))
            for row in rows:
                expected = 0.250 if row["case"] == "direct" else 0.400
                self.assertEqual([expected], row["samples_ms"])
                self.assertIsNone(row["first_half_median_ms"])
                for field in ("median_ms", "min_ms", "max_ms", "second_half_median_ms"):
                    self.assertEqual(expected, row[field])
        for flags in ((), ("--summary-only",), ("--sample-limit", "1"),
                      ("--sample-limit", "5"), ("--all-languages",),
                      ("--summary-only", "--all-languages"),
                      ("--sample-limit", "1", "--all-languages")):
            with self.subTest(flags=flags):
                result = self.run_cli(path, extra=flags)
                self.assertEqual(0, result.returncode, result.stderr)
                size = 6 if "--all-languages" in flags else 2
                self.assertEqual(size, result.stdout.count("前半 算出不可"))
                self.assertIn("中央値 0.25, 最小 0.25, 最大 0.25, 前半 算出不可, 後半 0.25", result.stdout)
                if "--summary-only" in flags:
                    self.assertEqual(size, result.stdout.count("件数 1"))
                    self.assertNotIn("samples_ms (", result.stdout)
                else:
                    self.assertEqual(size, result.stdout.count("samples_ms (1-1): 1:"))
        self.assertEqual(before, self.file_hashes(path))

    def test_single_and_multi_sample_archives_keep_order(self) -> None:
        first = self.make_archive("20260801_130000", count=1)
        second = self.make_archive("20260802_130000", count=3)
        before = self.file_hashes(first, second)
        for flags in (("--json", "--all-languages"), ("--all-languages",),
                      ("--summary-only", "--all-languages"),
                      ("--sample-limit", "1", "--all-languages")):
            result = self.run_cli(second, first, extra=flags)
            self.assertEqual(0, result.returncode, result.stderr)
            if "--json" in flags:
                runs = json.loads(result.stdout)["runs"]
                self.assertEqual([str(second), str(first)], [run["path"] for run in runs])
                self.assertEqual(["c", "c", "javascript", "javascript", "python", "python"],
                                 [row["language"] for row in runs[1]["cases"]])
                self.assertTrue(all(row["first_half_median_ms"] is None for row in runs[1]["cases"]))
                self.assertTrue(all(row["first_half_median_ms"] is not None for row in runs[0]["cases"]))
            else:
                self.assertLess(result.stdout.index(f"履歴 1: {second}"),
                                result.stdout.index(f"履歴 2: {first}"))
                self.assertEqual(6, result.stdout.count("前半 算出不可"))
        self.assertEqual(before, self.file_hashes(first, second))

    def test_two_odd_and_fifty_samples_keep_split_statistics(self) -> None:
        for count in (2, 3, 5, 50):
            with self.subTest(count=count):
                path = self.make_archive(f"20260801_{count:06d}", count=count)
                result = self.run_cli(path, extra=("--json", "--all-languages"))
                self.assertEqual(0, result.returncode, result.stderr)
                for row in json.loads(result.stdout)["runs"][0]["cases"]:
                    samples = row["samples_ms"]
                    self.assertEqual(count, len(samples))
                    self.assertEqual(statistics.median(samples), row["median_ms"])
                    self.assertEqual(statistics.median(samples[:count // 2]), row["first_half_median_ms"])
                    self.assertEqual(statistics.median(samples[count // 2:]), row["second_half_median_ms"])

    def test_empty_samples_and_zero_count_rejected_after_rehash(self) -> None:
        for count in (0, 1):
            path = self.make_archive(f"20260801_{count:06d}", count=1)
            def empty(document):
                document["config"]["measurement_iterations"] = count
                for result in document["results"].values():
                    result["samples_ms"] = []
            ShowArchiveMetricsTests.rewrite(path, "c.json", empty)
            before = self.file_hashes(path)
            for flags in ((), ("--json",), ("--summary-only",), ("--sample-limit", "1")):
                result = self.run_cli(path, extra=flags)
                self.assertEqual(2, result.returncode)
                self.assertNotIn("IndexError", result.stderr)
                if "--json" in flags:
                    self.assertEqual({"error"}, set(json.loads(result.stdout)))
                else:
                    self.assertEqual("", result.stdout)
            self.assertEqual(before, self.file_hashes(path))

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

    def test_sample_limit_restricts_text_to_first_n_without_changing_full_statistics(self) -> None:
        path = self.make_archive("20260801_130000")
        before = {file.name: file.read_bytes() for file in path.iterdir() if file.is_file()}
        baseline = self.run_cli(path)
        limited = self.run_cli(path, extra=("--sample-limit", "3"))
        self.assertEqual(0, limited.returncode, limited.stderr)
        self.assertIn("samples_ms (1-3 of 50): 1:0.1, 2:0.1, 3:0.1", limited.stdout)
        self.assertIn("samples_ms (1-3 of 50): 1:0.4, 2:0.4, 3:0.4", limited.stdout)
        self.assertNotIn("4:0.1", limited.stdout)
        self.assertIn("中央値 0.175, 最小 0.1, 最大 0.25, 前半 0.1, 後半 0.25",
                      limited.stdout)
        self.assertNotIn("samples_ms (1-50)", limited.stdout)
        self.assertEqual(baseline.stdout, self.run_cli(path, extra=("--sample-limit", "50")).stdout)
        self.assertEqual(baseline.stdout, self.run_cli(path, extra=("--sample-limit", "500")).stdout)
        self.assertEqual(before, {file.name: file.read_bytes() for file in path.iterdir() if file.is_file()})

    def test_sample_limit_multiple_archives_all_languages_preserves_order(self) -> None:
        first = self.make_archive("20260801_130000")
        second = self.make_archive("20260802_130000", low=0.200, high=0.300)
        report = self.run_cli(second, first, extra=("--all-languages", "--sample-limit", "1"))
        self.assertEqual(0, report.returncode, report.stderr)
        self.assertTrue(report.stdout.index(f"履歴 1: {second}") <
                        report.stdout.index(f"履歴 2: {first}"))
        self.assertEqual(12, report.stdout.count("samples_ms (1-1 of 50): 1:"))
        self.assertNotIn("2:0.", report.stdout)

    def test_sample_limit_invalid_and_conflicting_flags_fail_before_loading(self) -> None:
        missing = self.root / "missing"
        for flags in (("--sample-limit", "0"), ("--sample-limit", "-1"),
                      ("--sample-limit", "abc"), ("--sample-limit", "2", "--json"),
                      ("--json", "--sample-limit", "2"),
                      ("--summary-only", "--sample-limit", "2")):
            with self.subTest(flags=flags):
                result = self.run_cli(missing, extra=flags)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("--sample-limit", result.stderr)

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

    def test_case_json_keeps_contract_order_and_full_statistics(self) -> None:
        paths = [self.make_archive(f"202608{day:02d}_130000", count=count)
                 for day, count in enumerate((1, 2, 5, 50), 1)]
        before = self.file_hashes(*paths)
        for all_languages in ((), ("--all-languages",)):
            original = self.run_cli(*reversed(paths), extra=("--json", *all_languages))
            self.assertEqual(0, original.returncode, original.stderr)
            baseline = json.loads(original.stdout)
            for case in ("direct", "function_call"):
                result = self.run_cli(*reversed(paths), extra=("--json", "--case", case, *all_languages))
                self.assertEqual((0, ""), (result.returncode, result.stderr))
                expected = json.loads(original.stdout)
                for run in expected["runs"]:
                    run["cases"] = [row for row in run["cases"] if row["case"] == case]
                self.assertEqual(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", result.stdout)
                report = json.loads(result.stdout)
                self.assertEqual(list(baseline), list(report))
                for run, count in zip(report["runs"], (50, 5, 2, 1)):
                    self.assertEqual(["c", "javascript", "python"] if all_languages else ["c"],
                                     [row["language"] for row in run["cases"]])
                    samples = ([0.100] * (count // 2) + [0.250] * (count - count // 2)
                               if case == "direct" else [0.400] * count)
                    for row in run["cases"]:
                        self.assertEqual(samples, row["samples_ms"])
                        self.assertEqual(count, len(row["samples_ms"]))
                        self.assertEqual(statistics.median(samples), row["median_ms"])
                        self.assertEqual(min(samples), row["min_ms"])
                        self.assertEqual(max(samples), row["max_ms"])
                        self.assertEqual(statistics.median(samples[:count // 2]) if count > 1 else None,
                                         row["first_half_median_ms"])
                        self.assertEqual(statistics.median(samples[count // 2:]), row["second_half_median_ms"])
        self.assertEqual(before, self.file_hashes(*paths))

    def test_case_text_modes_only_remove_unselected_rows(self) -> None:
        first = self.make_archive("20260801_130000", count=1)
        second = self.make_archive("20260802_130000", count=50)
        before = self.file_hashes(first, second)
        for languages in ((), ("--all-languages",)):
            for mode in ((), ("--summary-only",), ("--sample-limit", "1"),
                         ("--sample-limit", "3"), ("--sample-limit", "500")):
                baseline = self.run_cli(second, first, extra=(*mode, *languages))
                self.assertEqual(0, baseline.returncode, baseline.stderr)
                for case in ("direct", "function_call"):
                    selected = self.run_cli(second, first, extra=("--case", case, *mode, *languages))
                    expected, keep = [], True
                    for line in baseline.stdout.splitlines():
                        if line.startswith("  ") and not line.startswith("    "):
                            keep = f"/{case}:" in line
                        elif not line.startswith("    "):
                            keep = True
                        if keep:
                            expected.append(line)
                    self.assertEqual((0, "\n".join(expected) + "\n", ""),
                                     (selected.returncode, selected.stdout, selected.stderr))
        self.assertEqual(before, self.file_hashes(first, second))

    def test_case_rejects_hidden_content_after_rehash_and_hash_tampering(self) -> None:
        for selected, hidden in (("direct", "function_call"), ("function_call", "direct")):
            for language in ("c", "python"):
                for rehash in (False, True):
                    with self.subTest(selected=selected, language=language, rehash=rehash):
                        path = self.make_archive(f"20260801_{len(list(self.root.glob('*_c.json'))):06d}")
                        def damage(document):
                            document["results"][hidden]["samples_ms"][0] = -1
                        if rehash:
                            ShowArchiveMetricsTests.rewrite(path, f"{language}.json", damage)
                        else:
                            file = path / f"{language}.json"
                            document = json.loads(file.read_text(encoding="utf-8"))
                            damage(document)
                            file.write_text(json.dumps(document), encoding="utf-8")
                        before = self.file_hashes(path)
                        for mode in ((), ("--json",), ("--summary-only",), ("--sample-limit", "1")):
                            result = self.run_cli(path, extra=("--case", selected, *mode))
                            self.assertEqual(2, result.returncode)
                            if "--json" in mode:
                                error = json.loads(result.stdout)
                                self.assertEqual({"error"}, set(error))
                                code = error["error"]["code"]
                            else:
                                self.assertEqual("", result.stdout)
                                code = result.stderr
                            self.assertIn("RESULT_VALIDATION_FAILED" if rehash else "SHA256_MISMATCH", code)
                        self.assertEqual(before, self.file_hashes(path))

    def test_case_invalid_values_conflicts_and_duplicate_archives(self) -> None:
        missing = self.root / "missing"
        for flags in (("--case", "unknown"), ("--case", ""), ("--case",),
                      ("--case=",), ("--case", "direct", "--summary-only", "--json"),
                      ("--case", "function_call", "--sample-limit", "1", "--json"),
                      ("--case", "direct", "--sample-limit", "1", "--summary-only"),
                      ("--case", "direct", "--sample-limit", "0")):
            with self.subTest(flags=flags):
                # Value-missing must be tested without a positional argument that could consume it.
                paths = () if flags == ("--case",) else (missing,)
                result = self.run_cli(*paths, extra=flags)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("error:", result.stderr)
                self.assertNotIn("検証エラー", result.stderr)
        path = self.make_archive("20260801_130000")
        copied = self.root / "copy" / path.parent.name / path.name
        shutil.copytree(path, copied)
        before = self.file_hashes(path, copied)
        for other in (path, copied):
            for case in ("direct", "function_call"):
                result = self.run_cli(path, other, extra=("--case", case, "--json"))
                self.assertEqual(2, result.returncode)
                self.assertEqual("DUPLICATE_ARCHIVE", json.loads(result.stdout)["error"]["code"])
        self.assertEqual(before, self.file_hashes(path, copied))


if __name__ == "__main__":
    unittest.main()
