import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tools import validate_result_json
from tools.extract_function_call_findings import (
    analyze_c_artifacts,
    analyze_python_bytecode,
    analyze_v8_trace,
)
from tools.validate_result_json import (
    OPTIMIZATION_RESULTS,
    ROOT_KEYS,
    ROOT_KEYS_WITH_OPTIMIZATION,
    normalize_legacy_result,
    validate,
    validate_analysis_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATHS = [
    PROJECT_ROOT / "results" / f"jit_object_numeric_sum_{language}_result.json"
    for language in ("python", "javascript", "c")
]
PYTHON_BENCHMARK_PATH = PROJECT_ROOT / "benchmarks" / "function_call_numeric_sum" / "python" / "main.py"
PYTHON_BENCHMARK_SPEC = importlib.util.spec_from_file_location("function_call_python", PYTHON_BENCHMARK_PATH)
PYTHON_BENCHMARK = importlib.util.module_from_spec(PYTHON_BENCHMARK_SPEC)
PYTHON_BENCHMARK_SPEC.loader.exec_module(PYTHON_BENCHMARK)


def build_optimization_analysis() -> dict:
    condition = {
        "source_sha256": "a" * 64,
        "implementation": {"name": "CPython", "version": "3.14.7"},
        "architecture": "amd64",
        "options": ["optimize=0"],
    }
    artifact_findings = {
        "inlining": {"result": "not_checked"},
        "vectorization": {"result": "unknown"},
        "simd": {"result": "not_checked", "isa": []},
    }
    return {
        "implementation": {"name": "CPython", "version": "3.14.7"},
        "provenance": {
            "status": "matched",
            "artifact_id": "function-call-analysis-test-python",
            "analyzed_at": "2026-08-31T12:00:00Z",
            "applies_to": ["inlining", "vectorization", "simd"],
            "analysis": copy.deepcopy(condition),
            "artifact_findings": copy.deepcopy(artifact_findings),
            "current": copy.deepcopy(condition),
            "matched": True,
            "mismatches": [],
        },
        "jit": {"applicable": True, "result": "not_detected"},
        "inlining": copy.deepcopy(artifact_findings["inlining"]),
        "vectorization": copy.deepcopy(artifact_findings["vectorization"]),
        "simd": copy.deepcopy(artifact_findings["simd"]),
        "other_optimizations": [],
        "evidence": [{"type": "runtime_api", "path": "python:sys._jit.is_available/is_enabled"}],
        "notes": [],
    }


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

    def test_analysis_manifest_is_valid_and_matches_sources(self) -> None:
        path = PROJECT_ROOT / "artifacts" / "function-call-analysis" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], validate_analysis_manifest(manifest, path))
        sources = {
            "c": PROJECT_ROOT / "benchmarks" / "function_call_numeric_sum" / "c" / "main.c",
            "python": PYTHON_BENCHMARK_PATH,
            "javascript": PROJECT_ROOT / "benchmarks" / "function_call_numeric_sum" / "javascript" / "main.js",
        }
        for language, source in sources.items():
            with self.subTest(language=language):
                actual = hashlib.sha256(source.read_bytes()).hexdigest()
                self.assertEqual(actual, manifest["languages"][language]["condition"]["source_sha256"])

    def test_findings_are_derived_from_artifact_content(self) -> None:
        report = "main.c:73: optimized: loop vectorized using 16 byte vectors\n"
        assembly = """
direct_sum:
    pxor xmm1, xmm1
    paddq xmm1, xmm0
    ret
    .seh_endproc
function_call_sum:
    call \"add\"
    ret
    .seh_endproc
"""
        findings = analyze_c_artifacts(report, assembly, "x64")
        self.assertEqual({"result": "not_detected"}, findings["inlining"])
        self.assertEqual({"result": "detected"}, findings["vectorization"])
        self.assertEqual({"result": "detected", "isa": ["SSE2"]}, findings["simd"])
        self.assertEqual({"result": "not_checked", "isa": []}, analyze_c_artifacts(report, assembly, "arm64")["simd"])
        self.assertEqual("not_checked", analyze_c_artifacts(report, assembly.replace("paddq", "add"), "x64")["vectorization"]["result"])

        trace = """
[completed optimizing 0x1 <JSFunction called (sfi = 0x2)> (target TURBOFAN_JS) OSR]
Inlining 0x1 {0x2 <SharedFunctionInfo add>} into 0x3 {0x4 <SharedFunctionInfo called>}
"""
        self.assertEqual("detected", analyze_v8_trace(trace)["jit"]["result"])
        self.assertEqual("detected", analyze_v8_trace(trace)["inlining"]["result"])
        self.assertEqual("not_checked", analyze_v8_trace("unrelated trace")["jit"]["result"])
        self.assertEqual("not_checked", analyze_v8_trace("unrelated trace")["inlining"]["result"])

        bytecode = """
Disassembly of <code object function_call at 0x1, file \"main.py\", line 1>:
  FOR_ITER 10
  LOAD_GLOBAL 1 (add)
  CALL 2
Disassembly of <code object other at 0x2, file \"main.py\", line 2>:
"""
        self.assertEqual("not_detected", analyze_python_bytecode(bytecode)["inlining"]["result"])
        self.assertEqual("not_detected", analyze_python_bytecode(bytecode)["vectorization"]["result"])

    def test_malformed_manifest_entries_are_unavailable(self) -> None:
        current = {
            "source_sha256": "a" * 64,
            "implementation": {"name": "CPython", "version": "3.14.7"},
            "architecture": "amd64",
            "options": ["optimize=0"],
        }
        valid_entry = {
            "artifact_id": "test-python",
            "analyzed_at": "2026-08-31T12:00:00Z",
            "applies_to": ["inlining", "vectorization", "simd"],
            "condition": copy.deepcopy(current),
            "generation_commands": ["python", "-m", "dis", "main.py"],
            "findings": {
                "inlining": {"result": "not_detected"},
                "vectorization": {"result": "not_detected"},
                "simd": {"result": "not_checked", "isa": []},
            },
            "evidence": [{"type": "disassembly", "path": "bytecode.txt"}],
        }
        cases = {
            "manifest missing": None,
            "entry object missing": {},
            "condition missing": {key: value for key, value in valid_entry.items() if key != "condition"},
            "findings missing": {key: value for key, value in valid_entry.items() if key != "findings"},
            "implementation string": {**valid_entry, "condition": {**current, "implementation": "CPython"}},
            "evidence string": {**valid_entry, "evidence": "bytecode.txt"},
        }
        for name, entry in cases.items():
            with self.subTest(name=name):
                result = PYTHON_BENCHMARK.optimization_analysis(copy.deepcopy(entry), copy.deepcopy(current), None)
                self.assertEqual("unavailable", result["provenance"]["status"])
                self.assertIsNone(result["provenance"]["artifact_findings"])
                self.assertEqual("unknown", result["inlining"]["result"])
                self.assertEqual("unknown", result["vectorization"]["result"])
                self.assertEqual({"result": "unknown", "isa": []}, result["simd"])

        malformed = PYTHON_BENCHMARK.optimization_analysis(PYTHON_BENCHMARK.parse_manifest_entry("{"), copy.deepcopy(current), None)
        self.assertEqual(["manifest_invalid"], malformed["provenance"]["mismatches"])
        missing_language = PYTHON_BENCHMARK.optimization_analysis(PYTHON_BENCHMARK.parse_manifest_entry('{"languages": {}}'), copy.deepcopy(current), None)
        self.assertEqual(["manifest_invalid"], missing_language["provenance"]["mismatches"])
        self.assertIsNone(PYTHON_BENCHMARK.load_manifest_entry(PROJECT_ROOT / "missing-manifest.json"))

    def test_python_runner_validates_the_complete_manifest(self) -> None:
        manifest_path = PROJECT_ROOT / "artifacts" / "function-call-analysis" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        current = copy.deepcopy(manifest["languages"]["python"]["condition"])
        self.assertEqual([], validate_analysis_manifest(manifest, manifest_path))
        valid = PYTHON_BENCHMARK.optimization_analysis(
            PYTHON_BENCHMARK.parse_manifest_entry(json.dumps(manifest)), current, None
        )
        self.assertEqual("matched", valid["provenance"]["status"])

        cases = {
            "schema version": lambda d: d.update(schema_version="2.0"),
            "analysis id missing": lambda d: d.pop("analysis_id"),
            "generated at invalid": lambda d: d.update(generated_at="not-a-timestamp"),
            "languages array": lambda d: d.update(languages=[]),
            "languages null": lambda d: d.update(languages=None),
            "sibling missing": lambda d: d["languages"].pop("javascript"),
            "unknown root field": lambda d: d.update(unexpected=True),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(manifest)
                mutate(candidate)
                self.assertTrue(validate_analysis_manifest(candidate, Path(name)))
                analysis = PYTHON_BENCHMARK.optimization_analysis(
                    PYTHON_BENCHMARK.parse_manifest_entry(json.dumps(candidate)), copy.deepcopy(current), None
                )
                provenance = analysis["provenance"]
                self.assertEqual("unavailable", provenance["status"])
                self.assertFalse(provenance["matched"])
                self.assertEqual(["manifest_invalid"], provenance["mismatches"])
                for field in ("artifact_id", "analyzed_at", "analysis", "artifact_findings"):
                    self.assertIsNone(provenance[field])
                self.assertEqual("unknown", analysis["inlining"]["result"])
                self.assertEqual("unknown", analysis["vectorization"]["result"])
                self.assertEqual({"result": "unknown", "isa": []}, analysis["simd"])
                self.assertEqual([], analysis["evidence"])

    def test_validator_rejects_malformed_provenance_without_raising(self) -> None:
        base = build_error_document()
        document = {key: build_optimization_analysis() if key == "optimization_analysis" else base[key] for key in ROOT_KEYS_WITH_OPTIMIZATION}
        cases = {
            "applies_to null": lambda p: p.update(applies_to=None),
            "analysis null": lambda p: p.update(analysis=None),
            "current array": lambda p: p.update(current=[]),
            "analysis implementation string": lambda p: p["analysis"].update(implementation="CPython"),
            "current options null": lambda p: p["current"].update(options=None),
            "findings null": lambda p: p.update(artifact_findings=None),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(document)
                mutate(candidate["optimization_analysis"]["provenance"])
                self.assertTrue(validate(candidate, Path(name)))

    def test_validator_compares_current_values_with_artifact_findings(self) -> None:
        base = build_error_document()
        document = {key: build_optimization_analysis() if key == "optimization_analysis" else base[key] for key in ROOT_KEYS_WITH_OPTIMIZATION}
        candidate = copy.deepcopy(document)
        candidate["optimization_analysis"]["inlining"]["result"] = "detected"
        self.assertTrue(validate(candidate, Path("matched-findings-differ")))

        candidate = copy.deepcopy(document)
        provenance = candidate["optimization_analysis"]["provenance"]
        provenance.update(status="mismatched", matched=False, mismatches=["architecture"])
        provenance["current"]["architecture"] = "arm64"
        candidate["optimization_analysis"]["inlining"] = copy.deepcopy(provenance["artifact_findings"]["inlining"])
        self.assertTrue(validate(candidate, Path("mismatch-reused-findings")))

    def test_manifest_validator_is_type_safe(self) -> None:
        path = PROJECT_ROOT / "artifacts" / "function-call-analysis" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        cases = {
            "languages null": lambda d: d.update(languages=None),
            "applies null": lambda d: d["languages"]["python"].update(applies_to=None),
            "condition null": lambda d: d["languages"]["python"].update(condition=None),
            "implementation string": lambda d: d["languages"]["python"]["condition"].update(implementation="CPython"),
            "options null": lambda d: d["languages"]["python"]["condition"].update(options=None),
            "findings null": lambda d: d["languages"]["python"].update(findings=None),
            "evidence string": lambda d: d["languages"]["python"].update(evidence="bytecode.txt"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(manifest)
                mutate(candidate)
                self.assertTrue(validate_analysis_manifest(candidate, Path(name)))

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

    def test_optional_optimization_analysis_is_validated(self) -> None:
        analysis = build_optimization_analysis()
        base = build_error_document()
        document = {
            key: analysis if key == "optimization_analysis" else base[key]
            for key in ROOT_KEYS_WITH_OPTIMIZATION
        }
        self.assertEqual([], validate(document, Path("optimization.json")))
        self.assertEqual(ROOT_KEYS_WITH_OPTIMIZATION, list(document))
        self.assertIsInstance(document["optimization_analysis"]["simd"]["isa"], list)
        self.assertEqual([], document["optimization_analysis"]["other_optimizations"])

        for result in OPTIMIZATION_RESULTS:
            with self.subTest(result=result):
                candidate = copy.deepcopy(document)
                candidate["optimization_analysis"]["inlining"]["result"] = result
                candidate["optimization_analysis"]["provenance"]["artifact_findings"]["inlining"]["result"] = result
                self.assertEqual([], validate(candidate, Path(result)))

        invalid_cases = {
            "unexpected result": lambda d: d["optimization_analysis"]["inlining"].update(result="maybe"),
            "simd isa scalar": lambda d: d["optimization_analysis"]["simd"].update(isa="SSE2"),
            "detected simd without isa": lambda d: d["optimization_analysis"]["simd"].update(result="detected", isa=[]),
            "unchecked simd with isa": lambda d: d["optimization_analysis"]["simd"].update(result="not_checked", isa=["SSE2"]),
            "duplicate simd isa": lambda d: d["optimization_analysis"]["simd"].update(result="detected", isa=["SSE2", "SSE2"]),
            "empty implementation": lambda d: d["optimization_analysis"]["implementation"].update(version=""),
            "false applicable result": lambda d: d["optimization_analysis"]["jit"].update(applicable=False, result="not_checked"),
            "true not applicable": lambda d: d["optimization_analysis"]["jit"].update(applicable=True, result="not_applicable"),
            "evidence object": lambda d: d["optimization_analysis"].update(evidence={}),
            "other object": lambda d: d["optimization_analysis"].update(other_optimizations={}),
            "conclusive without evidence": lambda d: d["optimization_analysis"].update(evidence=[]),
        }
        for name, mutate in invalid_cases.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(document)
                mutate(candidate)
                self.assertTrue(validate(candidate, Path(name)))

    def test_provenance_mismatch_downgrades_saved_findings(self) -> None:
        current = {
            "source_sha256": "a" * 64,
            "implementation": {"name": "CPython", "version": "3.14.7"},
            "architecture": "amd64",
            "options": ["optimize=0"],
        }
        entry = {
            "artifact_id": "test-python",
            "analyzed_at": "2026-08-31T12:00:00Z",
            "applies_to": ["inlining", "vectorization", "simd"],
            "condition": copy.deepcopy(current),
            "generation_commands": ["python", "-m", "dis", "main.py"],
            "findings": {
                "inlining": {"result": "not_detected"},
                "vectorization": {"result": "not_detected"},
                "simd": {"result": "not_checked", "isa": []},
            },
            "evidence": [{"type": "disassembly", "path": "artifacts/function-call-analysis/python-bytecode.txt"}],
        }
        matched = PYTHON_BENCHMARK.optimization_analysis(entry, copy.deepcopy(current), None)
        self.assertTrue(matched["provenance"]["matched"])
        self.assertEqual("not_detected", matched["inlining"]["result"])
        self.assertEqual("not_detected", matched["vectorization"]["result"])

        cases = {
            "source_sha256": lambda condition: condition.update(source_sha256="b" * 64),
            "implementation.version": lambda condition: condition["implementation"].update(version="3.13.0"),
            "architecture": lambda condition: condition.update(architecture="arm64"),
            "implementation.name": lambda condition: condition["implementation"].update(name="PyPy"),
        }
        for mismatch, mutate in cases.items():
            with self.subTest(mismatch=mismatch):
                changed = copy.deepcopy(current)
                mutate(changed)
                result = PYTHON_BENCHMARK.optimization_analysis(entry, changed, None)
                self.assertFalse(result["provenance"]["matched"])
                self.assertIn(mismatch, result["provenance"]["mismatches"])
                self.assertEqual("not_checked", result["inlining"]["result"])
                self.assertEqual("not_checked", result["vectorization"]["result"])

    def test_python_jit_classification_is_injectable(self) -> None:
        class Jit:
            def __init__(self, available=True, enabled=False, error=None):
                self.available, self.enabled, self.error = available, enabled, error
            def is_available(self):
                if self.error == "available": raise RuntimeError("unavailable")
                return self.available
            def is_enabled(self):
                if self.error == "enabled": raise RuntimeError("unavailable")
                return self.enabled

        self.assertEqual({"applicable": False, "result": "not_applicable"}, PYTHON_BENCHMARK.classify_jit(Jit(available=False)))
        self.assertEqual({"applicable": True, "result": "not_detected"}, PYTHON_BENCHMARK.classify_jit(Jit(available=True, enabled=False)))
        self.assertEqual({"applicable": True, "result": "unknown"}, PYTHON_BENCHMARK.classify_jit(Jit(available=True, enabled=True)))
        self.assertEqual({"applicable": True, "result": "unknown"}, PYTHON_BENCHMARK.classify_jit(Jit(error="available")))
        self.assertEqual({"applicable": True, "result": "unknown"}, PYTHON_BENCHMARK.classify_jit(Jit(error="enabled")))
        self.assertEqual({"applicable": True, "result": "not_checked"}, PYTHON_BENCHMARK.classify_jit(None))

    def test_mismatched_c_and_javascript_findings_are_not_conclusive(self) -> None:
        for language, mismatch, name in (("c", "architecture", "simd"), ("javascript", "options", "jit")):
            with self.subTest(language=language):
                analysis = build_optimization_analysis()
                analysis["provenance"]["applies_to"] = ["jit", "inlining", "vectorization", "simd"] if language == "javascript" else ["inlining", "vectorization", "simd"]
                if language == "javascript":
                    analysis["provenance"]["artifact_findings"]["jit"] = {"result": "detected"}
                analysis["provenance"]["status"] = "mismatched"
                analysis["provenance"]["matched"] = False
                analysis["provenance"]["mismatches"] = [mismatch]
                if mismatch == "architecture": analysis["provenance"]["current"]["architecture"] = "arm64"
                else: analysis["provenance"]["current"]["options"] = ["--jitless"]
                analysis[name]["result"] = "detected"
                if name == "simd": analysis[name]["isa"] = ["SSE2"]
                base = build_error_document(language)
                if language == "c":
                    base["build"] = {"required": True, "compiler": "gcc", "compiler_version": "gcc 16", "compile_command": "gcc -O2 main.c", "compile_ms": 1.0, "source_path": "main.c"}
                document = {key: analysis if key == "optimization_analysis" else base[key] for key in ROOT_KEYS_WITH_OPTIMIZATION}
                self.assertTrue(validate(document, Path(language)))

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

    def test_error_result_requires_all_null_statistics_and_timing_fields(self) -> None:
        cases = {
            "samples missing": lambda doc: doc["results"].pop("samples_ms"),
            "min numeric": lambda doc: doc["results"].update(min_ms=0.0),
            "min missing": lambda doc: doc["results"].pop("min_ms"),
            "max numeric": lambda doc: doc["results"].update(max_ms=0.0),
            "mean numeric": lambda doc: doc["results"].update(mean_ms=0.0),
            "median numeric": lambda doc: doc["results"].update(median_ms=0.0),
            "timing numeric": lambda doc: doc["timing"].update(setup_ms=0.0),
            "timing missing": lambda doc: doc["timing"].pop("setup_ms"),
            "passed missing": lambda doc: doc["validation"].pop("passed"),
            "error type missing": lambda doc: doc["error"].pop("type"),
            "error message missing": lambda doc: doc["error"].pop("message"),
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

    def test_legacy_normalization_variants_and_zero_values(self) -> None:
        cases = {
            "dict samples": (
                {"benchmark": "b", "config": {"item_count": 0, "measurement_iterations": 0}, "results": {"samples": [0.0], "min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}, "timing": {"total_ms": 0.0}, "validation": {"checksum": 0, "expected_checksum": 0}},
                {"item_count": 0, "measurement_iterations": 0, "samples_ms": [0.0], "measurement_ms": 0.0, "benchmark_total_ms": 0.0, "checksum": 0},
            ),
            "root samples": (
                {"experiment": "b", "object_count": 3, "repeat_count": 2, "samples_ms": [1.0], "total_ms": 1.0, "checksum": 1},
                {"item_count": 3, "measurement_iterations": 2, "samples_ms": [1.0], "benchmark_total_ms": 1.0, "checksum": 1},
            ),
            "data size": (
                {"data_size": 4, "iterations": 1, "samples": [2.0], "benchmark_total_ms": 2.0},
                {"item_count": 4, "measurement_iterations": 1, "samples_ms": [2.0], "benchmark_total_ms": 2.0},
            ),
            "empty list": ({"results": []}, {"samples_ms": [], "checksum": None, "measurement_ms": None}),
            "invalid": ({}, {"samples_ms": [], "item_count": None, "measurement_iterations": None}),
        }
        for name, (document, expected) in cases.items():
            with self.subTest(name=name):
                normalized = normalize_legacy_result(document)
                for key, value in expected.items():
                    self.assertEqual(value, normalized[key])

    def test_cli_rejects_inconsistent_and_unreadable_documents(self) -> None:
        base_documents = [json.loads(path.read_text(encoding="utf-8")) for path in RESULT_PATHS]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index, document in enumerate(base_documents):
                path = root / f"{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.append(path)

            def invoke(selected: list[Path]) -> int:
                old_argv = sys.argv
                try:
                    sys.argv = ["validate_result_json.py", *(str(path) for path in selected)]
                    return validate_result_json.main()
                finally:
                    sys.argv = old_argv

            self.assertEqual(0, invoke(paths))
            mismatch = copy.deepcopy(base_documents[1])
            mismatch["experiment_id"] = "20260802_130000_jit_object_numeric_sum"
            paths[1].write_text(json.dumps(mismatch), encoding="utf-8")
            self.assertEqual(1, invoke(paths))
            mismatch = copy.deepcopy(base_documents[1])
            mismatch["benchmark"] = "function_call_numeric_sum"
            paths[1].write_text(json.dumps(mismatch), encoding="utf-8")
            self.assertEqual(1, invoke(paths))
            duplicate = copy.deepcopy(base_documents[1])
            duplicate["language"] = "python"
            duplicate["run_id"] = "20260801_130001_python_jit_object_numeric_sum"
            paths[1].write_text(json.dumps(duplicate), encoding="utf-8")
            self.assertEqual(1, invoke(paths))
            paths[1].write_text("{", encoding="utf-8")
            self.assertEqual(1, invoke(paths))
            paths[1].write_text("[]", encoding="utf-8")
            self.assertEqual(1, invoke(paths))
            self.assertEqual(1, invoke([root / "missing.json"]))

            old_argv = sys.argv
            try:
                sys.argv = ["validate_result_json.py", "--manifest", str(PROJECT_ROOT / "artifacts" / "function-call-analysis" / "manifest.json")]
                self.assertEqual(0, validate_result_json.main())
            finally:
                sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
