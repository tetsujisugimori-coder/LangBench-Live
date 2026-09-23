import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_result_schema import build_optimization_analysis, function_call_document
from tools.archive_results import archive_results
from tools.compare_archives import ArchiveError, compare_archives, load_archive
from tools.validate_result_json import ROOT_KEYS_WITH_OPTIMIZATION, validate


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "tools" / "compare_archives.py"


def fixture_document(language: str, experiment_id: str) -> dict:
    document = function_call_document(language)
    document["experiment_id"] = experiment_id
    document["run_id"] = f"{experiment_id[:15]}_{language}_function_call_numeric_sum"
    document["environment"].update(os="Windows", os_version="10.0", cpu="Example CPU", architecture="AMD64")
    document["engine"].update(runtime="native" if language == "c" else language,
                              runtime_version=None if language == "c" else "1.0")
    if language == "python":
        document["engine"]["python_implementation"] = "CPython"
    if language == "javascript":
        document["engine"]["v8_version"] = "12.0"
    analysis = build_optimization_analysis()
    implementation = {"c": ("GCC", "gcc 15"), "javascript": ("V8", "12.0"), "python": ("CPython", "1.0")}[language]
    analysis["implementation"] = {"name": implementation[0], "version": implementation[1]}
    for condition in ("analysis", "current"):
        analysis["provenance"][condition]["implementation"] = copy.deepcopy(analysis["implementation"])
        analysis["provenance"][condition]["options"] = ["-O2"] if language == "c" else ["default"]
        analysis["provenance"][condition]["source_sha256"] = {"c": "a", "javascript": "b", "python": "c"}[language] * 64
    if language == "c":
        analysis["jit"] = {"applicable": False, "result": "not_applicable"}
    if language == "javascript":
        analysis["provenance"]["applies_to"] = ["jit", "inlining", "vectorization", "simd"]
        analysis["provenance"]["artifact_findings"]["jit"] = {"result": analysis["jit"]["result"]}
    document = {key: analysis if key == "optimization_analysis" else document[key]
                for key in ROOT_KEYS_WITH_OPTIMIZATION}
    errors = validate(document, Path("fixture.json"))
    assert not errors, errors
    return document


class CompareArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def make_archive(self, stamp: str, mutate=None, definition_mutate=None) -> Path:
        experiment_id = f"{stamp}_function_call_numeric_sum"
        sources = []
        for language in ("c", "javascript", "python"):
            document = fixture_document(language, experiment_id)
            if mutate:
                mutate(document)
            path = self.root / f"{stamp}_{language}.json"
            path.write_text(json.dumps(document) + "\n", encoding="utf-8")
            sources.append(path)
        definition = {
            "schema_version": "1.0", "benchmark": "function_call_numeric_sum",
            "languages": ["c", "javascript", "python"],
            "config": fixture_document("python", experiment_id)["config"], "expected_checksum": 3,
        }
        if definition_mutate:
            definition_mutate(definition)
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
        elif name != "archive.json":
            for entry in index["results"]:
                if entry["file"] == name:
                    entry["sha256"] = hashlib.sha256(raw).hexdigest()
        if name != "archive.json":
            index_path.write_text(json.dumps(index), encoding="utf-8")

    def test_same_conditions_and_metadata_differences_are_comparable(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        # JSON formatting and definition key order change the byte hash, not conditions.
        path = right / "experiment.json"
        reordered = dict(reversed(list(json.loads(path.read_text(encoding="utf-8")).items())))
        path.write_text(json.dumps(reordered, indent=4) + "\n", encoding="utf-8")
        index_path = right / "archive.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["experiment_manifest"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index), encoding="utf-8")
        result = compare_archives(load_archive(left), load_archive(right))
        self.assertEqual({"verdict": "comparable", "reasons": []}, result)
        completed = subprocess.run([sys.executable, str(COMMAND), "--json", str(left), str(right)],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("comparable", json.loads(completed.stdout)["verdict"])

    def test_rehashed_condition_difference_is_incomparable_not_corrupt(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        # Change a valid condition and every saved result, then update all four hashes.
        self.rewrite(right, "experiment.json", lambda d: d["config"].update(warmup_iterations=2))
        for language in ("c", "javascript", "python"):
            self.rewrite(right, f"{language}.json", lambda d: d["config"].update(warmup_iterations=2))
        result = compare_archives(load_archive(left), load_archive(right))
        self.assertEqual("incomparable", result["verdict"])
        self.assertEqual(["config"], [r["field"] for r in result["reasons"]])
        self.rewrite(right, "experiment.json", lambda d: d.update(schema_version="2.0"))
        self.assertEqual({"config", "schema_version"},
                         {r["field"] for r in compare_archives(load_archive(left), load_archive(right))["reasons"]})

    def test_environment_source_and_missing_information_are_cautions(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "python.json", lambda d: d["environment"].update(os="Linux"))
        self.rewrite(right, "javascript.json", lambda d: d["optimization_analysis"]["provenance"]["current"].update(source_sha256="d" * 64))
        # A source difference remains a valid result when analysis provenance is downgraded.
        def downgrade(d):
            p = d["optimization_analysis"]["provenance"]
            p.update(status="mismatched", matched=False, mismatches=["source_sha256"])
            d["optimization_analysis"]["jit"]["result"] = "not_checked"
            for name in ("inlining", "vectorization", "simd"):
                d["optimization_analysis"][name]["result"] = "not_checked"
        self.rewrite(right, "javascript.json", downgrade)
        self.rewrite(right, "c.json", lambda d: d["environment"].update(cpu=None))
        result = compare_archives(load_archive(left), load_archive(right))
        self.assertEqual("caution", result["verdict"])
        self.assertEqual({"ENVIRONMENT_DIFFERENT", "INFORMATION_MISSING"}, {r["code"] for r in result["reasons"]})
        self.assertIn("optimization_analysis.provenance.current.source_sha256", {r["field"] for r in result["reasons"]})

    def test_compiler_option_difference_is_caution(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        def mutate(d):
            p = d["optimization_analysis"]["provenance"]
            p["current"]["options"] = ["-O3"]
            p.update(status="mismatched", matched=False, mismatches=["options"])
            for name in ("inlining", "vectorization", "simd"):
                d["optimization_analysis"][name]["result"] = "not_checked"
        self.rewrite(right, "c.json", mutate)
        result = compare_archives(load_archive(left), load_archive(right))
        self.assertEqual("caution", result["verdict"])
        self.assertIn("optimization_analysis.provenance.current.options", {r["field"] for r in result["reasons"]})

    def test_missing_source_information_is_caution(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        self.rewrite(right, "python.json", lambda d: d.pop("optimization_analysis"))
        result = compare_archives(load_archive(left), load_archive(right))
        self.assertEqual("caution", result["verdict"])
        self.assertIn("optimization_analysis.provenance.current.source_sha256",
                      {r["field"] for r in result["reasons"]})

    def test_corruption_missing_duplicate_and_invalid_reference_are_errors(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        (right / "python.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ArchiveError, "SHA-256 mismatch"):
            load_archive(right)
        right = self.make_archive("20260803_130000")
        (right / "python.json").unlink()
        with self.assertRaisesRegex(ArchiveError, "missing"):
            load_archive(right)
        self.rewrite(left, "archive.json", lambda d: d["results"][1].update(file="../python.json"))
        with self.assertRaisesRegex(ArchiveError, "invalid file reference"):
            load_archive(left)
        self.rewrite(left, "archive.json", lambda d: d["results"][1].update(file="c.json"))
        with self.assertRaises(ArchiveError) as caught:
            load_archive(left)
        self.assertEqual("DUPLICATE_FILE", caught.exception.code)
        self.rewrite(left, "archive.json", lambda d: d["results"][1].update(language="c"))
        with self.assertRaisesRegex(ArchiveError, "duplicate language"):
            load_archive(left)

    def test_broken_json_and_cli_error_are_distinct_from_verdict(self) -> None:
        left = self.make_archive("20260801_130000")
        right = self.make_archive("20260802_130000")
        (right / "archive.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ArchiveError) as caught:
            load_archive(right)
        self.assertEqual("INVALID_JSON", caught.exception.code)
        completed = subprocess.run([sys.executable, str(COMMAND), "--json", str(left), str(right)],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("INVALID_JSON", json.loads(completed.stdout)["error"]["code"])
        self.assertNotIn("verdict", json.loads(completed.stdout))
        (right / "archive.json").write_text('{"archive_id":"x","archive_id":"y"}', encoding="utf-8")
        with self.assertRaises(ArchiveError) as caught:
            load_archive(right)
        self.assertEqual("DUPLICATE_JSON_KEY", caught.exception.code)

    def test_validation_failure_and_definition_mismatch_are_errors(self) -> None:
        folder = self.make_archive("20260801_130000")
        self.rewrite(folder, "c.json", lambda d: d["validation"].update(passed=False))
        with self.assertRaises(ArchiveError) as caught:
            load_archive(folder)
        self.assertEqual("RESULT_VALIDATION_FAILED", caught.exception.code)
        folder = self.make_archive("20260802_130000")
        self.rewrite(folder, "experiment.json", lambda d: d["config"].update(warmup_iterations=2))
        with self.assertRaises(ArchiveError) as caught:
            load_archive(folder)
        self.assertEqual("RESULT_DEFINITION_MISMATCH", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
