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
from tools.show_archive_metrics import format_number


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

    def test_language_selection_all_modes_statistics_order_and_hashes(self) -> None:
        paths = [self.make_archive(f"202609{day:02d}_130000", count=count)
                 for day, count in enumerate((1, 2, 5, 50), 1)]
        # Deliberately unsorted samples distinguish sample order from median order.
        for path in paths:
            for language in ("c", "javascript", "python"):
                def reorder(document):
                    for row in document["results"].values():
                        row["samples_ms"].reverse()
                ShowArchiveMetricsTests.rewrite(path, f"{language}.json", reorder)
        before = self.file_hashes(*paths)
        ordered = tuple(reversed(paths))
        for case in ((), ("--case", "direct"), ("--case", "function_call")):
            original = self.run_cli(*ordered, extra=(*case, "--json", "--all-languages"))
            self.assertEqual(0, original.returncode, original.stderr)
            for language in ("c", "python", "javascript"):
                result = self.run_cli(*ordered, extra=(*case, "--json", "--language", language))
                expected = json.loads(original.stdout)
                for run in expected["runs"]:
                    run["cases"] = [row for row in run["cases"] if row["language"] == language]
                self.assertEqual((0, json.dumps(expected, ensure_ascii=False, indent=2) + "\n", ""),
                                 (result.returncode, result.stdout, result.stderr))
                for run, count in zip(json.loads(result.stdout)["runs"], (50, 5, 2, 1)):
                    for row in run["cases"]:
                        samples = list(reversed([0.100] * (count // 2) + [0.250] * (count - count // 2)))
                        if row["case"] == "function_call":
                            samples = [0.400] * count
                        self.assertEqual(samples, row["samples_ms"])
                        midpoint = count // 2
                        for key, value in (("median_ms", statistics.median(samples)),
                                           ("min_ms", min(samples)), ("max_ms", max(samples)),
                                           ("first_half_median_ms", statistics.median(samples[:midpoint])
                                            if midpoint else None),
                                           ("second_half_median_ms", statistics.median(samples[midpoint:]))):
                            self.assertEqual(value, row[key])
                for mode in ((), ("--summary-only",), ("--sample-limit", "1"),
                             ("--sample-limit", "3"), ("--sample-limit", "500")):
                    baseline = self.run_cli(*ordered, extra=(*case, *mode, "--all-languages"))
                    selected = self.run_cli(*ordered, extra=(*case, *mode, "--language", language))
                    expected_lines, keep = [], True
                    for line in baseline.stdout.splitlines():
                        if line.startswith("  ") and not line.startswith("    "):
                            keep = line.startswith(f"  {language}/")
                        elif not line.startswith("    "):
                            keep = True
                        if keep:
                            expected_lines.append(line)
                    self.assertEqual((0, "\n".join(expected_lines) + "\n", ""),
                                     (selected.returncode, selected.stdout, selected.stderr))
        self.assertEqual(before, self.file_hashes(*paths))

    def test_language_rejects_hidden_language_and_case_corruption(self) -> None:
        for selected in ("c", "python", "javascript"):
            for damaged in ("c", "python", "javascript"):
                for rehash in (False, True):
                    with self.subTest(selected=selected, damaged=damaged, rehash=rehash):
                        path = self.make_archive(f"20260901_{len(list(self.root.glob('*_c.json'))):06d}")
                        def damage(document):
                            document["results"]["function_call"]["samples_ms"][0] = -1
                        if rehash:
                            ShowArchiveMetricsTests.rewrite(path, f"{damaged}.json", damage)
                        else:
                            file = path / f"{damaged}.json"
                            document = json.loads(file.read_text(encoding="utf-8"))
                            damage(document)
                            file.write_text(json.dumps(document), encoding="utf-8")
                        before = self.file_hashes(path)
                        for mode in ((), ("--json",), ("--summary-only",), ("--sample-limit", "1")):
                            result = self.run_cli(path, extra=("--language", selected, "--case", "direct", *mode))
                            self.assertEqual(2, result.returncode)
                            code = json.loads(result.stdout)["error"]["code"] if "--json" in mode else result.stderr
                            self.assertIn("RESULT_VALIDATION_FAILED" if rehash else "SHA256_MISMATCH", code)
                        self.assertEqual(before, self.file_hashes(path))

    def test_language_invalid_conflicting_and_duplicate_inputs(self) -> None:
        missing = self.root / "missing"
        flags_list = [("--language", "unknown"), ("--language", ""), ("--language=",),
                      ("--language",), ("--language", "python", "--summary-only", "--json"),
                      ("--language", "python", "--sample-limit", "0"),
                      ("--language", "python", "--sample-limit", "1", "--json"),
                      ("--language", "python", "--sample-limit", "1", "--summary-only")]
        for language in ("c", "python", "javascript"):
            flags_list.extend((("--language", language, "--all-languages"),
                               ("--all-languages", f"--language={language}")))
        for flags in flags_list:
            with self.subTest(flags=flags):
                result = self.run_cli(*(() if flags == ("--language",) else (missing,)), extra=flags)
                self.assertEqual((2, ""), (result.returncode, result.stdout))
                self.assertIn("error:", result.stderr)
                self.assertNotIn("検証エラー", result.stderr)
        path = self.make_archive("20260901_130000")
        copied = self.root / "copy" / path.parent.name / path.name
        shutil.copytree(path, copied)
        before = self.file_hashes(path, copied)
        for language in ("c", "python", "javascript"):
            for other in (path, copied):
                result = self.run_cli(path, other, extra=("--language", language, "--json"))
                self.assertEqual(2, result.returncode)
                self.assertEqual("DUPLICATE_ARCHIVE", json.loads(result.stdout)["error"]["code"])
        self.assertEqual(before, self.file_hashes(path, copied))

    def test_offset_ranges_all_columns_statistics_and_input_preservation(self) -> None:
        paths = [self.make_archive(f"20261001_{count:06d}", count=count) for count in (1, 2, 5, 50)]
        # Deliberately unsorted sequences make order/half-statistic errors visible.
        for path in paths:
            for language in ("c", "javascript", "python"):
                def reorder(document):
                    for row in document["results"].values():
                        row["samples_ms"].reverse()
                ShowArchiveMetricsTests.rewrite(path, f"{language}.json", reorder)
        paths.reverse()
        before = self.file_hashes(*paths)
        for language_flags in ((), ("--language", "c"), ("--language", "javascript"),
                               ("--language", "python"), ("--all-languages",)):
            languages = ("c", "javascript", "python") if "--all-languages" in language_flags else (
                language_flags[-1] if language_flags else "c",)
            for case_flags in ((), ("--case", "direct"), ("--case", "function_call")):
                cases = (case_flags[-1],) if case_flags else ("direct", "function_call")
                baseline = self.run_cli(*paths, extra=(*language_flags, *case_flags))
                self.assertEqual(0, baseline.returncode, baseline.stderr)
                statistics_lines = [line for line in baseline.stdout.splitlines()
                                    if not line.startswith("    samples_ms")]
                expected_rows = []
                for path, count in zip(paths, (50, 5, 2, 1)):
                    for language in languages:
                        for case in cases:
                            samples = ([0.400] * count if case == "function_call" else
                                       [0.250] * (count - count // 2) + [0.100] * (count // 2))
                            midpoint = count // 2
                            half = statistics.median(samples[:midpoint]) if midpoint else None
                            expected_stats = (f"  {language}/{case}: 中央値 {format_number(statistics.median(samples))}, "
                                              f"最小 {format_number(min(samples))}, 最大 {format_number(max(samples))}, "
                                              f"前半 {format_number(half) if half is not None else '算出不可'}, "
                                              f"後半 {format_number(statistics.median(samples[midpoint:]))}")
                            self.assertIn(expected_stats, statistics_lines)
                            expected_rows.append(samples)
                for offset in (0, 1, 2, 4, 5, 25, 49, 50, 51):
                    for limit in (None, 1, 3, 100):
                        with self.subTest(language=language_flags, case=case_flags, offset=offset, limit=limit):
                            limit_flags = () if limit is None else ("--sample-limit", str(limit))
                            result = self.run_cli(*paths, extra=(*language_flags, *case_flags,
                                                                "--sample-offset", str(offset), *limit_flags))
                            self.assertEqual((0, ""), (result.returncode, result.stderr))
                            self.assertEqual(statistics_lines, [line for line in result.stdout.splitlines()
                                                               if not line.startswith("    samples_ms")])
                            lines = [line for line in result.stdout.splitlines() if line.startswith("    samples_ms")]
                            self.assertEqual(len(expected_rows), len(lines))
                            for line, samples in zip(lines, expected_rows):
                                # Compute by enumerated source positions, not the implementation's slice.
                                numbered = [(i, value) for i, value in enumerate(samples, 1)
                                            if i > offset and (limit is None or i <= offset + limit)]
                                self.assertEqual(
                                    ", ".join(f"{i}:{format_number(value)}" for i, value in numbered),
                                    line.split(": ", 1)[1])
                                if not numbered:
                                    self.assertIn(f"(empty of {len(samples)})", line)
                                elif offset:
                                    self.assertIn(f"({numbered[0][0]}-{numbered[-1][0]} of {len(samples)})", line)
                            if offset == 0:
                                legacy = self.run_cli(*paths, extra=(*language_flags, *case_flags, *limit_flags))
                                self.assertEqual(legacy.stdout, result.stdout)
        self.assertEqual(before, self.file_hashes(*paths))

    def test_offset_rejects_skipped_and_hidden_corruption_before_output(self) -> None:
        valid = self.make_archive("20261002_000000", count=5)
        for rehash in (False, True):
            for language in ("c", "javascript", "python"):
                for case in ("direct", "function_call"):
                    path = self.make_archive(f"20261002_{len(list(self.root.glob('*_c.json'))):06d}", count=5)
                    def damage(document):
                        document["results"][case]["samples_ms"][0] = -1
                    if rehash:
                        ShowArchiveMetricsTests.rewrite(path, f"{language}.json", damage)
                    else:
                        file = path / f"{language}.json"
                        document = json.loads(file.read_text(encoding="utf-8"))
                        damage(document)
                        file.write_text(json.dumps(document), encoding="utf-8")
                    before = self.file_hashes(valid, path)
                    for offset in (1, 10):
                        result = self.run_cli(valid, path, extra=("--language", "c", "--case", "direct",
                                                                  "--sample-offset", str(offset), "--sample-limit", "1"))
                        self.assertEqual((2, ""), (result.returncode, result.stdout))
                        self.assertIn("RESULT_VALIDATION_FAILED" if rehash else "SHA256_MISMATCH", result.stderr)
                    self.assertEqual(before, self.file_hashes(valid, path))

    def test_offset_invalid_conflicting_and_duplicate_inputs(self) -> None:
        missing = self.root / "missing"
        invalid = [("--sample-offset", value) for value in ("-1", "1.5", "abc", "")]
        invalid.extend((("--sample-offset=",), ("--sample-offset",)))
        for value in ("0", "1"):
            for mode in ("--json", "--summary-only"):
                invalid.extend((("--sample-offset", value, mode), (mode, f"--sample-offset={value}")))
        invalid.extend((("--sample-offset", "0", "--sample-limit", "0"),
                        ("--sample-offset", "0", "--language", "c", "--all-languages"),
                        ("--sample-offset", "0", "--case", "bad")))
        for flags in invalid:
            result = self.run_cli(*(() if flags == ("--sample-offset",) else (missing,)), extra=flags)
            self.assertEqual((2, ""), (result.returncode, result.stdout))
            self.assertIn("error:", result.stderr)
            self.assertNotIn("検証エラー", result.stderr)
        path = self.make_archive("20261003_000000", count=5)
        copy = self.root / "copy" / path.parent.name / path.name
        shutil.copytree(path, copy)
        before = self.file_hashes(path, copy)
        for other in (path, copy):
            result = self.run_cli(path, other, extra=("--sample-offset", "50"))
            self.assertEqual((2, ""), (result.returncode, result.stdout))
            self.assertIn("DUPLICATE_ARCHIVE", result.stderr)
        self.assertEqual(before, self.file_hashes(path, copy))

    def test_offset_help_and_legacy_limit_abbreviations(self) -> None:
        help_result = self.run_cli(extra=("--help",))
        self.assertEqual(0, help_result.returncode)
        for text in ("--sample-offset N", "non-negative", "N+1", "archive/language/case",
                     "empty list", "statistics use all samples", "explicit 0"):
            self.assertIn(text, " ".join(help_result.stdout.split()))
        path = self.make_archive("20261004_000000", count=50)
        baseline = self.run_cli(path, extra=("--sample-limit", "3"))
        for flag in ("--sam", "--sample", "--sample-", "--sample-l"):
            self.assertEqual(baseline.stdout, self.run_cli(path, extra=(flag, "3")).stdout)
        result = self.run_cli(path, extra=("--sample-o=10", "--sample-limit", "5"))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("(11-15 of 50): 11:0.1, 12:0.1, 13:0.1, 14:0.1, 15:0.1", result.stdout)

    def test_per_line_ranges_columns_statistics_and_hashes(self) -> None:
        paths = [self.make_archive(f"20261005_{count:06d}", count=count) for count in (50, 5, 1)]
        for path in paths:
            for language in ("c", "javascript", "python"):
                def reverse(document):
                    for row in document["results"].values():
                        row["samples_ms"].reverse()
                ShowArchiveMetricsTests.rewrite(path, f"{language}.json", reverse)
        before = self.file_hashes(*paths)
        for language in ((), ("--all-languages",), ("--language", "javascript"),
                         ("--language", "python")):
            for case in ((), ("--case", "direct"), ("--case", "function_call")):
                for offset, limit in ((0, None), (10, 5), (1, 3), (50, None), (51, 2)):
                    flags = (*language, *case, "--sample-offset", str(offset))
                    if limit is not None:
                        flags += ("--sample-limit", str(limit))
                    baseline = self.run_cli(*paths, extra=flags)
                    self.assertEqual((0, ""), (baseline.returncode, baseline.stderr))
                    # The JSON oracle retains source order and all values, before display slicing.
                    report = json.loads(self.run_cli(*paths, extra=(*language, *case, "--json")).stdout)
                    rows = [row for run in report["runs"] for row in run["cases"]]
                    for width in (1, 2, 5, 100):
                        with self.subTest(language=language, case=case, offset=offset, limit=limit, width=width):
                            result = self.run_cli(*paths, extra=(*flags, "--samples-per-line", str(width)))
                            self.assertEqual((0, ""), (result.returncode, result.stderr))
                            lines = result.stdout.splitlines()
                            self.assertEqual([s for s in baseline.stdout.splitlines() if not s.startswith("    ")],
                                             [s for s in lines if not s.startswith("    ")])
                            headers = [i for i, s in enumerate(lines) if s.startswith("    samples_ms")]
                            self.assertEqual(len(rows), len(headers))
                            for row, index in zip(rows, headers):
                                expected = [f"{i}:{format_number(value)}"
                                            for i, value in enumerate(row["samples_ms"], 1)
                                            if i > offset and (limit is None or i <= offset + limit)]
                                prefix, first = lines[index].split(": ", 1)
                                column = len(prefix) + 2
                                data = [first]
                                for line in lines[index + 1:]:
                                    if not line.startswith(" " * column):
                                        break
                                    self.assertEqual(column, len(line) - len(line.lstrip()))
                                    data.append(line[column:])
                                self.assertEqual(max(1, (len(expected) + width - 1) // width), len(data))
                                self.assertTrue(all(not s.endswith(",") for s in data))
                                self.assertTrue(all(len(s.split(", ")) <= width for s in data))
                                actual = [item for line in data for item in line.split(", ") if item]
                                self.assertEqual(expected, actual)
                                if not expected:
                                    self.assertIn(f"empty of {len(row['samples_ms'])}", prefix)
        self.assertEqual(before, self.file_hashes(*paths))

    def test_per_line_rejects_invalid_and_conflicting_arguments(self) -> None:
        invalid = [("--samples-per-line", value) for value in ("0", "-1", "1.5", "abc", "")]
        invalid += [("--samples-per-line=",), ("--samples-per-line",)]
        for mode in ("--json", "--summary-only"):
            invalid += [(mode, "--samples-per-line=2"), ("--samples-per-line", "1", mode)]
        for flags in invalid:
            result = self.run_cli(*(() if flags == ("--samples-per-line",) else (self.root / "missing",)),
                                  extra=flags)
            self.assertEqual((2, ""), (result.returncode, result.stdout))
            self.assertIn("error:", result.stderr)
            self.assertNotIn("検証エラー", result.stderr)
        help_result = self.run_cli(extra=("--help",))
        self.assertIn("--samples-per-line K", help_result.stdout)
        self.assertIn("positive integer, text only", " ".join(help_result.stdout.split()))

    def test_per_line_rejects_hidden_corruption_before_any_output(self) -> None:
        valid = self.make_archive("20261006_000000", count=5)
        for language, case in (("c", "direct"), ("c", "function_call"), ("python", "direct")):
            for rehash in (False, True):
                path = self.make_archive(f"20261006_{len(list(self.root.glob('*_c.json'))):06d}", count=5)
                def damage(document):
                    document["results"][case]["samples_ms"][0] = -1
                if rehash:
                    ShowArchiveMetricsTests.rewrite(path, f"{language}.json", damage)
                else:
                    file = path / f"{language}.json"
                    document = json.loads(file.read_text(encoding="utf-8"))
                    damage(document)
                    file.write_text(json.dumps(document), encoding="utf-8")
                before = self.file_hashes(valid, path)
                result = self.run_cli(valid, path, extra=("--language", "c", "--case", "direct",
                    "--sample-offset", "1", "--sample-limit", "1", "--samples-per-line", "2"))
                self.assertEqual((2, ""), (result.returncode, result.stdout))
                self.assertIn("RESULT_VALIDATION_FAILED" if rehash else "SHA256_MISMATCH", result.stderr)
                self.assertEqual(before, self.file_hashes(valid, path))

    def test_legacy_argument_errors_keep_usage_without_case_option(self) -> None:
        missing = self.root / "missing"
        for flags in (("--summary-only", "--json"), ("--sample-limit", "0"),
                      ("--sample-limit", "1", "--json"),
                      ("--sample-limit", "1", "--summary-only"),
                      ("--sample-limit", "bad"), ("--unknown",)):
            result = self.run_cli(missing, extra=flags)
            self.assertEqual((2, ""), (result.returncode, result.stdout))
            self.assertIn("usage:", result.stderr)
            self.assertNotIn("--case", result.stderr)
            self.assertNotIn("--language", result.stderr)
            self.assertNotIn("--sample-offset", result.stderr)
            self.assertNotIn("--samples-per-line", result.stderr)
        for flags in (("--case", "direct", "--sample-limit", "0"),
                      ("--cas=function_call", "--sample-limit", "0")):
            result = self.run_cli(missing, extra=flags)
            self.assertEqual(2, result.returncode)
            self.assertIn("[--case {direct,function_call}]", result.stderr)
            self.assertNotIn("--language", result.stderr)
        help_result = self.run_cli(extra=("--help",))
        self.assertEqual(0, help_result.returncode)
        self.assertIn("--case {direct,function_call}", help_result.stdout)
        self.assertIn("--language {c,javascript,python}", help_result.stdout)


if __name__ == "__main__":
    unittest.main()
