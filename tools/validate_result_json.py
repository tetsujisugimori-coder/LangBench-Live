import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT_KEYS = [
    "type", "schema_version", "project", "benchmark", "experiment_id", "run_id",
    "language", "created_at", "status", "engine", "execution", "environment",
    "config", "timing", "results", "validation", "error",
]
LANGUAGES = {"c", "python", "javascript"}
EXPERIMENT_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_jit_object_numeric_sum$")
RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_(c|python|javascript)_jit_object_numeric_sum$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def first(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


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
    if document.get("benchmark") != "jit_object_numeric_sum" or "experiment" in document:
        errors.append(f"{path}: invalid benchmark or deprecated experiment key")
    if document.get("language") not in LANGUAGES:
        errors.append(f"{path}: invalid language")
    if not EXPERIMENT_ID_PATTERN.fullmatch(document.get("experiment_id", "")):
        errors.append(f"{path}: invalid experiment_id")
    run_id_match = RUN_ID_PATTERN.fullmatch(document.get("run_id", ""))
    if not run_id_match or run_id_match.group(1) != document.get("language"):
        errors.append(f"{path}: invalid run_id")
    if not TIMESTAMP_PATTERN.fullmatch(document.get("created_at", "")):
        errors.append(f"{path}: created_at must include a timezone")
    if document.get("status") not in {"success", "error"}:
        errors.append(f"{path}: invalid status")

    config = document.get("config") or {}
    timing = document.get("timing") or {}
    results = document.get("results") or {}
    validation = document.get("validation") or {}
    samples = results.get("samples_ms") or []
    iterations = config.get("measurement_iterations")
    if len(samples) != iterations:
        errors.append(f"{path}: samples_ms length does not match measurement_iterations")
    if samples and not math.isclose(timing.get("measurement_ms"), sum(samples), abs_tol=0.01):
        errors.append(f"{path}: measurement_ms does not match samples_ms sum")
    if samples:
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
            if not math.isclose(results.get(name), expected, abs_tol=0.001):
                errors.append(f"{path}: results.{name} is inconsistent")
    timing_parts = [timing.get(name) for name in ("setup_ms", "warmup_ms", "measurement_ms")]
    if all(isinstance(value, (int, float)) for value in timing_parts):
        if not math.isclose(timing.get("benchmark_total_ms"), sum(timing_parts), abs_tol=0.01):
            errors.append(f"{path}: benchmark_total_ms does not match timing components")
    if document.get("status") == "success":
        if document.get("error") is not None:
            errors.append(f"{path}: successful result must have error: null")
        if validation.get("passed") is not True:
            errors.append(f"{path}: validation.passed is not true")
        if validation.get("checksum") != validation.get("expected_checksum"):
            errors.append(f"{path}: checksum mismatch")
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
        root_types = [{key: type(doc.get(key)).__name__ for key in ROOT_KEYS} for doc in documents]
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
