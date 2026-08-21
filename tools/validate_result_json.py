import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT_KEYS = ["type", "schema_version", "project", "benchmark", "experiment_id", "run_id", "language", "created_at", "status", "engine", "execution", "environment", "build", "config", "timing", "results", "validation", "error"]
LANGUAGES = {"c", "python", "javascript"}
BENCHMARKS = {"jit_object_numeric_sum", "function_call_numeric_sum"}
EXPERIMENT_ID_PATTERN = re.compile(r"^(\d{8}_\d{6})_(jit_object_numeric_sum|function_call_numeric_sum)$")
RUN_ID_PATTERN = re.compile(r"^(\d{8}_\d{6})_(c|python|javascript)_(jit_object_numeric_sum|function_call_numeric_sum)$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def first(mapping: Any, *names: str) -> Any:
    """Return the first present key without treating valid zero values as absent."""
    if not isinstance(mapping, dict):
        return None
    for name in names:
        if name in mapping:
            return mapping[name]
    return None

def normalize_legacy_result(document: dict[str, Any]) -> dict[str, Any]:
    """Keep the public legacy comparison helper used by existing consumers."""
    if not isinstance(document, dict):
        document = {}
    config = document.get("config")
    timing = document.get("timing")
    raw_results = document.get("results")
    validation = document.get("validation")

    if isinstance(raw_results, dict):
        samples = first(raw_results, "samples_ms", "samples")
    elif isinstance(raw_results, list):
        samples = [item.get("elapsed_ms") for item in raw_results if isinstance(item, dict)]
    else:
        samples = first(document, "samples_ms", "samples")
    if samples is None:
        samples = []

    legacy_checksums = [
        item.get("checksum")
        for item in raw_results
        if isinstance(item, dict) and item.get("checksum") is not None
    ] if isinstance(raw_results, list) else []
    measurement_ms = first(timing, "measurement_ms")
    if measurement_ms is None and samples:
        try:
            measurement_ms = round(sum(samples), 3)
        except TypeError:
            measurement_ms = None

    return {
        "benchmark": first(document, "benchmark", "experiment"),
        "item_count": first(config, "item_count", "array_size", "object_count", "data_size")
        if first(config, "item_count", "array_size", "object_count", "data_size") is not None
        else first(document, "item_count", "array_size", "object_count", "data_size"),
        "measurement_iterations": first(config, "measurement_iterations", "iterations", "repeat_count")
        if first(config, "measurement_iterations", "iterations", "repeat_count") is not None
        else first(document, "measurement_iterations", "iterations", "repeat_count"),
        "samples_ms": samples,
        "min_ms": first(raw_results, "min_ms", "min"),
        "max_ms": first(raw_results, "max_ms", "max"),
        "mean_ms": first(raw_results, "mean_ms", "mean"),
        "median_ms": first(raw_results, "median_ms", "median"),
        "measurement_ms": measurement_ms,
        "benchmark_total_ms": first(timing, "benchmark_total_ms", "total_ms")
        if first(timing, "benchmark_total_ms", "total_ms") is not None
        else first(document, "benchmark_total_ms", "total_ms"),
        "checksum": first(validation, "checksum")
        if first(validation, "checksum") is not None
        else (legacy_checksums[-1] if legacy_checksums else first(document, "checksum")),
        "expected_checksum": first(validation, "expected_checksum")
        if first(validation, "expected_checksum") is not None
        else first(document, "expected_checksum"),
    }

def validate_build(document: dict[str, Any], errors: list[str], path: Path) -> None:
    language, build = document.get("language"), document.get("build")
    if language in {"python", "javascript"}:
        if build is not None: errors.append(f"{path}: {language} build must be null")
    elif language == "c":
        if not isinstance(build, dict): errors.append(f"{path}: C build must be an object"); return
        if build.get("required") is not True: errors.append(f"{path}: C build.required must be true")
        for name in ("compiler", "compiler_version", "compile_command", "source_path"):
            if not isinstance(build.get(name), str) or not build[name].strip(): errors.append(f"{path}: C build.{name} must be a non-empty string")
        if not is_number(build.get("compile_ms")) or build["compile_ms"] < 0: errors.append(f"{path}: C build.compile_ms must be a non-negative finite number")

def validate_common(document: Any, path: Path) -> list[str]:
    if not isinstance(document, dict): return [f"{path}: root must be an object"]
    errors: list[str] = []
    if list(document) != ROOT_KEYS: errors.append(f"{path}: root keys/order do not match schema 1.0")
    if document.get("type") != "langbench_result" or document.get("schema_version") != "1.0": errors.append(f"{path}: invalid type or schema_version")
    benchmark = document.get("benchmark")
    if benchmark not in BENCHMARKS or "experiment" in document: errors.append(f"{path}: invalid benchmark or deprecated experiment key")
    if document.get("project") != "LangBench Live": errors.append(f"{path}: invalid project")
    language = document.get("language")
    if language not in LANGUAGES: errors.append(f"{path}: invalid language")
    experiment_match = EXPERIMENT_ID_PATTERN.fullmatch(document.get("experiment_id", "") if isinstance(document.get("experiment_id"), str) else "")
    if not experiment_match or experiment_match.group(2) != benchmark: errors.append(f"{path}: invalid experiment_id")
    run_match = RUN_ID_PATTERN.fullmatch(document.get("run_id", "") if isinstance(document.get("run_id"), str) else "")
    if not run_match or run_match.group(2) != language or run_match.group(3) != benchmark: errors.append(f"{path}: invalid run_id")
    if not TIMESTAMP_PATTERN.fullmatch(document.get("created_at", "") if isinstance(document.get("created_at"), str) else ""): errors.append(f"{path}: created_at must include a timezone")
    status = document.get("status")
    if status not in {"success", "error"}: errors.append(f"{path}: invalid status")
    if status == "success" and document.get("error") is not None: errors.append(f"{path}: successful result must have error: null")
    if status == "error":
        error = document.get("error")
        if not isinstance(error, dict) or not all(isinstance(error.get(name), str) and error[name].strip() for name in ("type", "message")):
            errors.append(f"{path}: error result requires type and message")
        results, timing, validation = document.get("results"), document.get("timing"), document.get("validation")
        required_statistics = ("samples_ms", "min_ms", "max_ms", "mean_ms", "median_ms")
        if (
            not isinstance(results, dict)
            or any(name not in results for name in required_statistics)
            or results.get("samples_ms") != []
            or any(results.get(name) is not None for name in required_statistics[1:])
        ):
            errors.append(f"{path}: error result samples must be empty")
        timing_names = ("process_startup_ms", "setup_ms", "warmup_ms", "measurement_ms", "benchmark_total_ms")
        if (
            not isinstance(timing, dict)
            or any(name not in timing for name in timing_names)
            or any(timing.get(name) is not None for name in timing_names)
        ):
            errors.append(f"{path}: error result timing must be null")
        if (
            not isinstance(validation, dict)
            or any(name not in validation for name in ("checksum", "expected_checksum", "tolerance", "passed"))
            or validation.get("passed") is not False
        ):
            errors.append(f"{path}: error result validation must fail")
    validate_build(document, errors, path)
    return errors

def statistics_errors(samples: Any, expected_count: Any, result: Any, case: str, path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict): return [f"{path}: {case} result must be an object"]
    if not isinstance(samples, list) or len(samples) != expected_count or not samples or not all(is_number(x) for x in samples): return [f"{path}: {case} samples are invalid"]
    ordered = sorted(samples); middle = len(ordered) // 2
    expected = {"min_ms": min(samples), "max_ms": max(samples), "mean_ms": sum(samples) / len(samples), "median_ms": ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2}
    for name, value in expected.items():
        if not is_number(result.get(name)) or not math.isclose(result[name], value, abs_tol=0.001): errors.append(f"{path}: {case}.{name} is inconsistent")
    return errors

def validate_function_call(document: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []; config, timing, results, validation = (document.get("config"), document.get("timing"), document.get("results"), document.get("validation"))
    if not isinstance(config, dict) or config.get("cases") != ["direct", "function_call"]: return [f"{path}: function-call config is invalid"]
    if not isinstance(results, dict): return [f"{path}: function-call results must be an object"]
    samples_total = 0.0
    for case in ("direct", "function_call"):
        result = results.get(case); samples = result.get("samples_ms") if isinstance(result, dict) else None
        errors.extend(statistics_errors(samples, config.get("measurement_iterations"), result, case, path))
        if isinstance(samples, list) and all(is_number(x) for x in samples): samples_total += sum(samples)
    if not isinstance(timing, dict): errors.append(f"{path}: timing must be an object")
    else:
        values = [timing.get(name) for name in ("setup_ms", "warmup_ms", "measurement_ms", "benchmark_total_ms")]
        if not all(is_number(x) for x in values): errors.append(f"{path}: timing values must be finite numbers")
        else:
            if not math.isclose(values[2], samples_total, abs_tol=0.01): errors.append(f"{path}: measurement_ms does not match samples")
            if not math.isclose(values[3], sum(values[:3]), abs_tol=0.01): errors.append(f"{path}: benchmark_total_ms does not match timing")
    if not isinstance(validation, dict) or validation.get("passed") is not True or validation.get("direct_checksum") != validation.get("function_call_checksum") or validation.get("direct_checksum") != validation.get("expected_checksum"): errors.append(f"{path}: case checksum validation failed")
    return errors

def validate_object_sum(document: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []; config, timing, results, validation = document.get("config"), document.get("timing"), document.get("results"), document.get("validation")
    if not isinstance(config, dict) or not isinstance(results, dict) or not isinstance(timing, dict) or not isinstance(validation, dict): return [f"{path}: benchmark sections must be objects"]
    samples = results.get("samples_ms"); errors.extend(statistics_errors(samples, config.get("measurement_iterations"), results, "results", path))
    if isinstance(samples, list) and all(is_number(x) for x in samples):
        if not is_number(timing.get("measurement_ms")) or not math.isclose(timing["measurement_ms"], sum(samples), abs_tol=0.01): errors.append(f"{path}: measurement_ms does not match samples")
    values = [timing.get(name) for name in ("setup_ms", "warmup_ms", "measurement_ms", "benchmark_total_ms")]
    if not all(is_number(x) for x in values) or not math.isclose(values[3], sum(values[:3]), abs_tol=0.01): errors.append(f"{path}: timing is invalid")
    if validation.get("passed") is not True or validation.get("checksum") != validation.get("expected_checksum"): errors.append(f"{path}: checksum validation failed")
    return errors

def validate(document: Any, path: Path) -> list[str]:
    errors = validate_common(document, path)
    if not isinstance(document, dict): return errors
    if document.get("status") == "error": return errors
    if document.get("benchmark") == "function_call_numeric_sum": errors.extend(validate_function_call(document, path))
    elif document.get("benchmark") == "jit_object_numeric_sum": errors.extend(validate_object_sum(document, path))
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("paths", nargs="+", type=Path); args = parser.parse_args()
    documents = []; errors: list[str] = []
    for path in args.paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"{path}: cannot read JSON: {error}"); continue
        documents.append(document); errors.extend(validate(document, path))
    valid_docs = [doc for doc in documents if isinstance(doc, dict)]
    if len(valid_docs) > 1:
        if len({doc.get("experiment_id") for doc in valid_docs}) != 1: errors.append("experiment_id differs between language results")
        if len({doc.get("benchmark") for doc in valid_docs}) != 1: errors.append("benchmark differs between language results")
        languages = [doc.get("language") for doc in valid_docs]
        if len(languages) != len(set(languages)): errors.append("language is duplicated between results")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors)); return 1
    print(f"validated={len(documents)}"); return 0
if __name__ == "__main__": raise SystemExit(main())
