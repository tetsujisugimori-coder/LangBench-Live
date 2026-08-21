import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT_KEYS = [
    "type", "schema_version", "project", "benchmark", "experiment_id", "run_id",
    "language", "created_at", "status", "engine", "execution", "environment",
    "build", "config", "timing", "results", "validation", "error",
]
LANGUAGES = {"c", "python", "javascript"}
EXPERIMENT_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_(jit_object_numeric_sum|function_call_numeric_sum)$")
RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_(c|python|javascript)_(jit_object_numeric_sum|function_call_numeric_sum)$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def first(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_legacy_result(document: dict[str, Any]) -> dict[str, Any]:
    """Return the comparison fields from either schema 1.0 or older result JSON."""
    config = document.get("config") or {}
    timing = document.get("timing") or {}
    raw_results = document.get("results")
    if isinstance(raw_results, dict):
        samples = first(raw_results, "samples_ms", "samples") or []
    elif isinstance(raw_results, list):
        samples = [item.get("elapsed_ms") for item in raw_results if isinstance(item, dict)]
    else:
        samples = document.get("samples_ms") or document.get("samples") or []
    validation = document.get("validation") or {}
    legacy_checksums = [
        item.get("checksum") for item in raw_results or []
        if isinstance(item, dict) and item.get("checksum") is not None
    ] if isinstance(raw_results, list) else []
    return {
        "benchmark": document.get("benchmark") or document.get("experiment"),
        "item_count": first(config, "item_count", "array_size", "object_count", "data_size")
        or first(document, "item_count", "array_size", "object_count", "data_size"),
        "measurement_iterations": first(config, "measurement_iterations", "iterations", "repeat_count")
        or first(document, "measurement_iterations", "iterations", "repeat_count"),
        "samples_ms": samples,
        "min_ms": first(raw_results, "min_ms", "min") if isinstance(raw_results, dict) else None,
        "max_ms": first(raw_results, "max_ms", "max") if isinstance(raw_results, dict) else None,
        "mean_ms": first(raw_results, "mean_ms", "mean") if isinstance(raw_results, dict) else None,
        "median_ms": first(raw_results, "median_ms", "median") if isinstance(raw_results, dict) else None,
        "measurement_ms": first(timing, "measurement_ms")
        or (round(sum(samples), 3) if samples else None),
        "benchmark_total_ms": first(timing, "benchmark_total_ms", "total_ms")
        or first(document, "benchmark_total_ms", "total_ms"),
        "checksum": validation.get("checksum")
        if "checksum" in validation else (legacy_checksums[-1] if legacy_checksums else document.get("checksum")),
        "expected_checksum": validation.get("expected_checksum", document.get("expected_checksum")),
    }


def validate(document: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    if list(document) != ROOT_KEYS:
        errors.append(f"{path}: root keys/order do not match schema 1.0")
    if document.get("type") != "langbench_result" or document.get("schema_version") != "1.0":
        errors.append(f"{path}: invalid type or schema_version")
    if document.get("benchmark") not in {"jit_object_numeric_sum", "function_call_numeric_sum"} or "experiment" in document:
        errors.append(f"{path}: invalid benchmark or deprecated experiment key")
    if document.get("language") not in LANGUAGES:
        errors.append(f"{path}: invalid language")
    if not EXPERIMENT_ID_PATTERN.fullmatch(document.get("experiment_id", "")):
        errors.append(f"{path}: invalid experiment_id")
    run_id_match = RUN_ID_PATTERN.fullmatch(document.get("run_id", ""))
    if not run_id_match or run_id_match.group(1) != document.get("language"):
        errors.append(f"{path}: invalid run_id")
    if document.get("benchmark") == "function_call_numeric_sum":
        return validate_function_call(document, path, errors)
    if not TIMESTAMP_PATTERN.fullmatch(document.get("created_at", "")):
        errors.append(f"{path}: created_at must include a timezone")
    if document.get("status") not in {"success", "error"}:
        errors.append(f"{path}: invalid status")

    language = document.get("language")
    build = document.get("build")
    if language in {"python", "javascript"}:
        if build is not None:
            errors.append(f"{path}: {language} build must be null")
    elif language == "c":
        if not isinstance(build, dict):
            errors.append(f"{path}: C build must be an object")
        else:
            if build.get("required") is not True:
                errors.append(f"{path}: C build.required must be true")
            for name in ("compiler", "compiler_version", "compile_command", "source_path"):
                if not isinstance(build.get(name), str) or not build[name].strip():
                    errors.append(f"{path}: C build.{name} must be a non-empty string")
            compile_ms = build.get("compile_ms")
            if not is_number(compile_ms) or compile_ms < 0:
                errors.append(f"{path}: C build.compile_ms must be a non-negative number")

    config = document.get("config") or {}
    timing = document.get("timing") or {}
    results = document.get("results") or {}
    validation = document.get("validation") or {}
    raw_samples = results.get("samples_ms")
    samples = raw_samples if isinstance(raw_samples, list) else []
    iterations = config.get("measurement_iterations")
    if document.get("status") == "success":
        if not isinstance(raw_samples, list):
            errors.append(f"{path}: successful result samples_ms must be an array")
        if len(samples) != iterations:
            errors.append(f"{path}: samples_ms length does not match measurement_iterations")
        if not samples:
            errors.append(f"{path}: successful result samples_ms must not be empty")
        if samples:
            measurement_ms = timing.get("measurement_ms")
            if not is_number(measurement_ms) or not math.isclose(measurement_ms, sum(samples), abs_tol=0.01):
                errors.append(f"{path}: measurement_ms does not match samples_ms sum")
            expected_statistics = {
                "min_ms": min(samples),
                "max_ms": max(samples),
                "mean_ms": sum(samples) / len(samples),
                "median_ms": (
                    sorted(samples)[len(samples) // 2]
                    if len(samples) % 2 else
                    sum(sorted(samples)[len(samples) // 2 - 1:len(samples) // 2 + 1]) / 2
                ),
            }
            for name, expected in expected_statistics.items():
                value = results.get(name)
                if not is_number(value) or not math.isclose(value, expected, abs_tol=0.001):
                    errors.append(f"{path}: results.{name} is inconsistent")
        timing_parts = [timing.get(name) for name in ("setup_ms", "warmup_ms", "measurement_ms")]
        benchmark_total_ms = timing.get("benchmark_total_ms")
        if not all(is_number(value) for value in timing_parts) or not is_number(benchmark_total_ms):
            errors.append(f"{path}: successful result timing values must be numbers")
        else:
            if not math.isclose(benchmark_total_ms, sum(timing_parts), abs_tol=0.01):
                errors.append(f"{path}: benchmark_total_ms does not match timing components")
        if document.get("error") is not None:
            errors.append(f"{path}: successful result must have error: null")
        if validation.get("passed") is not True:
            errors.append(f"{path}: validation.passed is not true")
        if validation.get("checksum") != validation.get("expected_checksum"):
            errors.append(f"{path}: checksum mismatch")
    elif document.get("status") == "error":
        if raw_samples != []:
            errors.append(f"{path}: error result must have an empty samples_ms array")
        for name in ("min_ms", "max_ms", "mean_ms", "median_ms"):
            if name not in results or results[name] is not None:
                errors.append(f"{path}: error result results.{name} must be null")
        for name in ("process_startup_ms", "setup_ms", "warmup_ms", "measurement_ms", "benchmark_total_ms"):
            if name not in timing or timing[name] is not None:
                errors.append(f"{path}: error result timing.{name} must be null")
        if validation.get("passed") is not False:
            errors.append(f"{path}: error result validation.passed must be false")
        error = document.get("error")
        if not isinstance(error, dict):
            errors.append(f"{path}: error result must contain an error object")
        else:
            for name in ("type", "message"):
                if not isinstance(error.get(name), str) or not error[name].strip():
                    errors.append(f"{path}: error.{name} must be a non-empty string")
    return errors


def validate_function_call(document: dict[str, Any], path: Path, errors: list[str]) -> list[str]:
    config, timing, results, validation = (document.get("config") or {}, document.get("timing") or {}, document.get("results") or {}, document.get("validation") or {})
    if config.get("cases") != ["direct", "function_call"]:
        errors.append(f"{path}: function-call cases are invalid")
    for case in ("direct", "function_call"):
        values = results.get(case) or {}; samples = values.get("samples_ms")
        if not isinstance(samples, list) or len(samples) != config.get("measurement_iterations") or not samples or not all(is_number(x) and math.isfinite(x) for x in samples):
            errors.append(f"{path}: {case} samples are invalid")
            continue
        expected = {"min_ms": min(samples), "max_ms": max(samples), "mean_ms": sum(samples) / len(samples), "median_ms": (sorted(samples)[len(samples)//2-1] + sorted(samples)[len(samples)//2]) / 2}
        for name, value in expected.items():
            if not is_number(values.get(name)) or not math.isclose(values[name], value, abs_tol=0.001): errors.append(f"{path}: {case}.{name} is inconsistent")
    timing_values = [timing.get(x) for x in ("setup_ms", "warmup_ms", "measurement_ms", "benchmark_total_ms")]
    if not all(is_number(x) and math.isfinite(x) for x in timing_values) or not math.isclose(timing_values[3], sum(timing_values[:3]), abs_tol=0.01): errors.append(f"{path}: timing is invalid")
    if not math.isclose(timing.get("measurement_ms", -1), sum(sum((results.get(c) or {}).get("samples_ms") or []) for c in ("direct", "function_call")), abs_tol=0.01): errors.append(f"{path}: measurement samples do not match")
    if validation.get("direct_checksum") != validation.get("function_call_checksum") or validation.get("direct_checksum") != validation.get("expected_checksum") or validation.get("passed") is not True: errors.append(f"{path}: case checksum validation failed")
    if document.get("status") != "success" or document.get("error") is not None: errors.append(f"{path}: function-call result must be successful")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LangBench result JSON schema 1.0")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    all_errors: list[str] = []
    documents = []
    for path in args.paths:
        with path.open(encoding="utf-8") as source:
            document = json.load(source)
        documents.append(document)
        all_errors.extend(validate(document, path))
    if documents:
        common_keys = [key for key in ROOT_KEYS if key != "build"]
        root_types = [{key: type(doc.get(key)).__name__ for key in common_keys} for doc in documents]
        if any(types != root_types[0] for types in root_types[1:]):
            all_errors.append("root key types differ between languages")
        experiment_ids = {doc.get("experiment_id") for doc in documents}
        if len(documents) > 1 and len(experiment_ids) != 1:
            all_errors.append("experiment_id differs between language results")
    if all_errors:
        for error in all_errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated={len(documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
