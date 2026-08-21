import copy
import json
import re
import unittest
from pathlib import Path

from tools.validate_result_json import ROOT_KEYS, normalize_legacy_result, validate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATHS = [
    PROJECT_ROOT / "results" / f"jit_object_numeric_sum_{language}_result.json"
    for language in ("python", "javascript", "c")
]


def build_error_document(language: str = "python") -> dict:
    return {
        "type": "langbench_result",
        "schema_version": "1.0",
        "project": "LangBench Live",
        "benchmark": "jit_object_numeric_sum",
        "experiment_id": "20260801_130000_jit_object_numeric_sum",
        "run_id": f"20260801_130001_{language}_jit_object_numeric_sum",
        "language": language,
        "created_at": "2026-08-01T13:00:01+09:00",
        "status": "error",
        "engine": {"runtime": language, "runtime_version": "test"},
        "execution": {"runner": None, "runner_label": None, "cwd": None, "argv": []},
        "environment": {
            "os": None,
            "os_version": None,
            "architecture": None,
            "cpu": None,
            "logical_processors": None,
            "memory_bytes": None,
        },
        "build": None,
        "config": {
            "item_count": 1_000_000,
            "warmup_iterations": 5,
            "measurement_iterations": 50,
            "numeric_type": "integer",
            "value_field": "value",
        },
        "timing": {
            "process_startup_ms": None,
            "setup_ms": None,
            "warmup_ms": None,
            "measurement_ms": None,
            "benchmark_total_ms": None,
        },
        "results": {
            "samples_ms": [],
            "min_ms": None,
            "max_ms": None,
            "mean_ms": None,
            "median_ms": None,
        },
        "validation": {
            "checksum": None,
            "expected_checksum": 500_000_500_000,
            "tolerance": 0,
            "passed": False,
        },
        "error": {"type": "RuntimeError", "message": "benchmark failed"},
    }


class ResultSchemaTests(unittest.TestCase):
    def test_function_call_documents_and_invalid_variants(self) -> None:
        def case_document(language: str) -> dict:
            samples = [1.0, 2.0]
            build = None if language != "c" else {"required": True, "compiler": "gcc", "compiler_version": "gcc 15", "compile_command": "gcc -O2 main.c", "compile_ms": 1.0, "source_path": "main.c"}
            return {
                "type": "langbench_result", "schema_version": "1.0", "project": "LangBench Live",
                "benchmark": "function_call_numeric_sum", "experiment_id": "20260801_130000_function_call_numeric_sum",
                "run_id": f"20260801_130001_{language}_function_call_numeric_sum", "language": language,
                "created_at": "2026-08-01T13:00:01+09:00", "status": "success",
                "engine": {"runtime": language}, "execution": {"runner": None, "runner_label": None, "cwd": None, "argv": []},
                "environment": {"os": None, "os_version": None, "architecture": None, "cpu": None, "logical_processors": None, "memory_bytes": None},
                "build": build, "config": {"item_count": 2, "warmup_iterations": 1, "measurement_iterations": 2, "numeric_type": "integer", "value_field": "value", "cases": ["direct", "function_call"]},
                "timing": {"process_startup_ms": None, "setup_ms": 1.0, "warmup_ms": 1.0, "measurement_ms": 6.0, "benchmark_total_ms": 8.0},
                "results": {case: {"samples_ms": samples, "min_ms": 1.0, "max_ms": 2.0, "mean_ms": 1.5, "median_ms": 1.5} for case in ("direct", "function_call")},
                "validation": {"direct_checksum": 3, "function_call_checksum": 3, "expected_checksum": 3, "tolerance": 0, "passed": True}, "error": None,
            }
        documents = [case_document(language) for language in ("python", "javascript", "c")]
        self.assertTrue(all(not validate(document, Path(language)) for document, language in zip(documents, ("python", "javascript", "c"))))
        invalid_cases = {
            "timezone": lambda d: d.update(created_at="2026-08-01T13:00:01"),
            "python build": lambda d: d.update(build={}),
            "id benchmark": lambda d: d.update(experiment_id="20260801_130000_jit_object_numeric_sum"),
            "run language": lambda d: d.update(run_id="20260801_130001_c_function_call_numeric_sum"),
            "case shape": lambda d: d["results"].update(direct=[]),
            "nan sample": lambda d: d["results"]["direct"].update(samples_ms=[float("nan"), 2.0]),
            "checksum": lambda d: d["validation"].update(function_call_checksum=4),
        }
        for name, mutate in invalid_cases.items():
            with self.subTest(name=name):
                document = copy.deepcopy(documents[0]); mutate(document)
                self.assertTrue(validate(document, Path(name)))
        c_document = documents[2]
        for name, mutate in {
            "missing build": lambda d: d.update(build=None),
            "empty compiler": lambda d: d["build"].update(compiler_version=""),
            "negative compile": lambda d: d["build"].update(compile_ms=-1),
        }.items():
            with self.subTest(name=name):
                document = copy.deepcopy(c_document); mutate(document)
                self.assertTrue(validate(document, Path(name)))
    def test_readme_json_example_is_parseable(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### 結果JSON正式仕様（schema 1.0）", 1)[1]
        match = re.search(r"```json\s+(.*?)\s+```", section, re.DOTALL)
        self.assertIsNotNone(match)
        document = json.loads(match.group(1))
        self.assertEqual(ROOT_KEYS, list(document))

    def test_tracked_samples_follow_formal_schema(self) -> None:
        documents = []
        for path in RESULT_PATHS:
            with self.subTest(path=path):
                document = json.loads(path.read_text(encoding="utf-8"))
                documents.append(document)
                self.assertEqual([], validate(document, path))
                self.assertEqual(ROOT_KEYS, list(document))
        self.assertEqual(1, len({document["experiment_id"] for document in documents}))
        common_keys = [key for key in ROOT_KEYS if key != "build"]
        root_types = [{key: type(document[key]) for key in common_keys} for document in documents]
        self.assertTrue(all(types == root_types[0] for types in root_types[1:]))
        for document in documents:
            if document["language"] == "c":
                self.assertIsInstance(document["build"], dict)
                self.assertTrue(document["build"]["required"])
                self.assertGreaterEqual(document["build"]["compile_ms"], 0)
            else:
                self.assertIsNone(document["build"])

    def test_formal_error_results_are_valid(self) -> None:
        for language in ("python", "javascript"):
            with self.subTest(language=language):
                self.assertEqual([], validate(build_error_document(language), Path(f"{language}-error.json")))

    def test_invalid_error_results_are_rejected(self) -> None:
        cases = {
            "null error": lambda doc: doc.update(error=None),
            "passed true": lambda doc: doc["validation"].update(passed=True),
            "samples present": lambda doc: doc["results"].update(samples_ms=[1.0]),
            "empty error type": lambda doc: doc["error"].update(type=""),
            "empty error message": lambda doc: doc["error"].update(message=""),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                document = copy.deepcopy(build_error_document())
                mutate(document)
                self.assertTrue(validate(document, Path("invalid-error.json")))

    def test_legacy_object_result_is_normalized(self) -> None:
        legacy = {
            "experiment": "jit_object_numeric_sum",
            "array_size": 3,
            "iterations": 2,
            "setup_ms": 1.0,
            "expected_checksum": 6,
            "results": [
                {"elapsed_ms": 0.25, "checksum": 6},
                {"elapsed_ms": 0.5, "checksum": 6},
            ],
            "timing": {"total_ms": 1.75},
        }
        normalized = normalize_legacy_result(legacy)
        self.assertEqual("jit_object_numeric_sum", normalized["benchmark"])
        self.assertEqual(3, normalized["item_count"])
        self.assertEqual(2, normalized["measurement_iterations"])
        self.assertEqual([0.25, 0.5], normalized["samples_ms"])
        self.assertEqual(0.75, normalized["measurement_ms"])
        self.assertEqual(1.75, normalized["benchmark_total_ms"])
        self.assertEqual(6, normalized["checksum"])
        self.assertEqual(6, normalized["expected_checksum"])


if __name__ == "__main__":
    unittest.main()
