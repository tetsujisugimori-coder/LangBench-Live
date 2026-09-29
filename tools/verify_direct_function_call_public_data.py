#!/usr/bin/env python3
"""Verify public direct/function_call samples against published aggregates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


LANGUAGES = ("c", "python", "javascript")
CASES = ("direct", "function_call")
SOURCES = {
    "c": Path("benchmarks/function_call_numeric_sum/c/main.c"),
    "python": Path("benchmarks/function_call_numeric_sum/python/main.py"),
    "javascript": Path("benchmarks/function_call_numeric_sum/javascript/main.js"),
}
SAMPLE_HEADERS = ["experiment_id", "run_id", "language", "case", "sample_order", "elapsed_ms"]
AGGREGATE_STATS = ("mean_ms", "median_ms", "sample_sd_ms", "min_ms", "max_ms")


def round_half_up(value: float, digits: int) -> float:
    """Match the declared public rule: half-up, at 3 decimals for ms / 6 for SD and ratios."""
    scale = 10**digits
    return math.floor(value * scale + 0.5) / scale


def sample_stats(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round_half_up(statistics.mean(samples), 3),
        "median_ms": round_half_up(statistics.median(samples), 3),
        "sample_sd_ms": round_half_up(statistics.stdev(samples), 6),
        "min_ms": round_half_up(min(samples), 3),
        "max_ms": round_half_up(max(samples), 3),
    }


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames or [], list(reader)


def _summary_row(language: str, direct: list[float], called: list[float], deltas: list[float], ratios: list[float]) -> str:
    labels = {"c": "C", "python": "Python", "javascript": "JavaScript"}
    fmt = lambda value: f"{value:.3f}"
    signed = lambda value: ("−" if value < 0 else "+") + fmt(abs(value))
    bound = lambda value: ("−" if value < 0 else "") + fmt(abs(value))
    row = [
        labels[language],
        "3",
        " / ".join(fmt(value) for value in direct),
        " / ".join(fmt(value) for value in called),
        " / ".join(signed(value) for value in deltas),
        f"{signed(statistics.median(deltas))} [{bound(min(deltas))}, {bound(max(deltas))}]",
        f"{statistics.median(ratios):.3f} [{min(ratios):.3f}, {max(ratios):.3f}]",
    ]
    return "| " + " | ".join(row) + " |"


def verify_public_data(output_dir: Path, manifest_path: Path) -> None:
    public = json.loads((output_dir / "public-data.json").read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    boundary = public.get("data_boundary", {})
    if (boundary.get("published_contains_sample_values") is not True
            or boundary.get("published_contains_full_raw_json") is not False
            or boundary.get("original_json_sha256_independently_recomputable_from_publication") is not False):
        raise ValueError("published-data boundary must distinguish samples from private full JSON")
    repo_root = manifest_path.resolve().parents[2]
    for language, relative in SOURCES.items():
        source_bytes = (repo_root / relative).read_bytes().replace(b"\r\n", b"\n")
        actual_sha = hashlib.sha256(source_bytes).hexdigest()
        if actual_sha != manifest["languages"][language]["condition"]["source_sha256"]:
            raise ValueError(f"current source SHA-256 differs from manifest: {language}")

    groups = public.get("experiments")
    if not isinstance(groups, list) or len(groups) != 3:
        raise ValueError("expected exactly three independent experiments")
    experiment_ids = [group.get("experiment_id") for group in groups]
    if len(set(experiment_ids)) != 3 or any(not value for value in experiment_ids):
        raise ValueError("experiment IDs must be unique and non-empty")

    headers, sample_rows = _load_csv(output_dir / "public-samples.csv")
    if headers != SAMPLE_HEADERS:
        raise ValueError(f"public-samples.csv columns mismatch: {headers}")
    expected_groups = {
        (experiment_id, language, case)
        for experiment_id in experiment_ids
        for language in LANGUAGES
        for case in CASES
    }
    values_by_key: dict[tuple[str, str, str], list[tuple[int, float, str]]] = {}
    for row in sample_rows:
        experiment_id, language, case = row["experiment_id"], row["language"], row["case"]
        key = (experiment_id, language, case)
        if key not in expected_groups:
            raise ValueError(f"unknown public sample group: {key}")
        try:
            sample_order = int(row["sample_order"])
            elapsed_ms = float(row["elapsed_ms"])
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid sample value/order: {key}") from error
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError(f"sample must be finite and non-negative: {key}")
        values_by_key.setdefault(key, []).append((sample_order, elapsed_ms, row["run_id"]))
    if set(values_by_key) != expected_groups or len(sample_rows) != 900:
        raise ValueError("expected 900 rows: 3 experiments × 3 languages × 2 cases × 50 samples")

    aggregate_headers, aggregate_rows = _load_csv(output_dir / "public-data.csv")
    if not aggregate_headers:
        raise ValueError("public-data.csv has no header")
    aggregate_by_key = {}
    for row in aggregate_rows:
        key = (row["experiment_id"], row["language"])
        if key in aggregate_by_key:
            raise ValueError(f"duplicate public aggregate row: {key}")
        aggregate_by_key[key] = row
    expected_aggregate_keys = {(experiment_id, language) for experiment_id in experiment_ids for language in LANGUAGES}
    if set(aggregate_by_key) != expected_aggregate_keys or len(aggregate_rows) != 9:
        raise ValueError("public-data.csv must contain exactly nine experiment-language rows")

    run_ids: set[str] = set()
    deltas_by_language = {language: [] for language in LANGUAGES}
    ratios_by_language = {language: [] for language in LANGUAGES}
    direct_medians = {language: [] for language in LANGUAGES}
    call_medians = {language: [] for language in LANGUAGES}
    for group in groups:
        experiment_id = group["experiment_id"]
        languages = group.get("languages")
        if not isinstance(languages, dict) or set(languages) != set(LANGUAGES):
            raise ValueError(f"expected all three languages for experiment {experiment_id}")
        for language in LANGUAGES:
            record = languages[language]
            if record.get("experiment_id") != experiment_id:
                raise ValueError("experiment ID mismatch in public JSON")
            run_id = record.get("run_id")
            if not run_id or run_id in run_ids:
                raise ValueError("run IDs must be unique and non-empty")
            run_ids.add(run_id)
            expected = manifest["languages"][language]
            condition = expected["condition"]
            if record.get("source_sha256") != condition["source_sha256"]:
                raise ValueError(f"source SHA mismatch: {experiment_id}/{language}")
            if record.get("implementation") != condition["implementation"] or record.get("architecture") != condition["architecture"] or record.get("options") != condition["options"]:
                raise ValueError(f"runtime/compiler condition mismatch: {experiment_id}/{language}")
            if record.get("analysis_artifact_id") != expected["artifact_id"] or record.get("analysis_findings") != expected["findings"]:
                raise ValueError(f"optimization finding mismatch: {experiment_id}/{language}")
            if record.get("sample_count_per_case") != 50:
                raise ValueError(f"declared sample count mismatch: {experiment_id}/{language}")
            checksums = record.get("checksums", {})
            if checksums.get("passed") is not True or checksums.get("direct_checksum") != 500000500000 or checksums.get("function_call_checksum") != 500000500000 or checksums.get("expected_checksum") != 500000500000 or checksums.get("tolerance") != 0:
                raise ValueError(f"checksum mismatch: {experiment_id}/{language}")
            if not isinstance(record.get("raw_sha256"), str) or len(record["raw_sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in record["raw_sha256"]):
                raise ValueError(f"invalid recorded original-JSON SHA-256: {experiment_id}/{language}")

            stats = {}
            for case in CASES:
                samples = sorted(values_by_key[(experiment_id, language, case)], key=lambda item: item[0])
                if len(samples) != 50 or [sample[0] for sample in samples] != list(range(1, 51)):
                    raise ValueError(f"sample order must be exactly 1..50: {experiment_id}/{language}/{case}")
                if any(sample[2] != run_id for sample in samples):
                    raise ValueError(f"experiment/run ID mapping mismatch: {experiment_id}/{language}/{case}")
                stats[case] = sample_stats([sample[1] for sample in samples])
                if record.get(case) != stats[case]:
                    raise ValueError(f"JSON aggregates do not match public samples: {experiment_id}/{language}/{case}")

            direct = stats["direct"]["median_ms"]
            called = stats["function_call"]["median_ms"]
            delta = round_half_up(called - direct, 3)
            ratio = round_half_up(called / direct, 6)
            if record.get("median_delta_call_minus_direct_ms") != delta or record.get("median_ratio_call_over_direct") != ratio:
                raise ValueError(f"per-run median delta/ratio mismatch: {experiment_id}/{language}")
            deltas_by_language[language].append(delta)
            ratios_by_language[language].append(ratio)
            direct_medians[language].append(direct)
            call_medians[language].append(called)

            row = aggregate_by_key[(experiment_id, language)]
            expected_text = {
                "run_id": run_id,
                "created_at": record["created_at"],
                "raw_sha256": record["raw_sha256"],
                "source_sha256": condition["source_sha256"],
                "analysis_artifact_id": expected["artifact_id"],
                "implementation": record["implementation"]["name"] + " " + record["implementation"]["version"],
                "architecture": condition["architecture"],
                "options": json.dumps(condition["options"], ensure_ascii=False, separators=(",", ":")),
                "analysis_findings": json.dumps(expected["findings"], ensure_ascii=False, separators=(",", ":")),
                "sample_count_per_case": "50",
            }
            for key, value in expected_text.items():
                if row.get(key) != str(value):
                    raise ValueError(f"aggregate CSV {key} mismatch: {experiment_id}/{language}")
            for case in CASES:
                for name, value in stats[case].items():
                    if float(row[f"{case}_{name}"]) != value:
                        raise ValueError(f"aggregate CSV {case}_{name} mismatch: {experiment_id}/{language}")
            if float(row["median_delta_call_minus_direct_ms"]) != delta or float(row["median_ratio_call_over_direct"]) != ratio:
                raise ValueError(f"aggregate CSV delta/ratio mismatch: {experiment_id}/{language}")

    for language in LANGUAGES:
        deltas, ratios = deltas_by_language[language], ratios_by_language[language]
        summary_record = public.get("language_summaries", {}).get(language)
        expected_summary = {
            "independent_experiment_count": 3,
            "within_run_samples_per_case": 50,
            "median_delta_ms_across_experiments": round_half_up(statistics.median(deltas), 3),
            "median_delta_ms_range": [min(deltas), max(deltas)],
            "median_ratio_across_experiments": round_half_up(statistics.median(ratios), 6),
            "median_ratio_range": [min(ratios), max(ratios)],
        }
        if summary_record != expected_summary:
            raise ValueError(f"JSON language summary mismatch: {language}")

    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    for language in LANGUAGES:
        label = {"c": "C", "python": "Python", "javascript": "JavaScript"}[language]
        matching = [line for line in summary_text.splitlines() if line.startswith(f"| {label} |")]
        expected_line = _summary_row(
            language,
            direct_medians[language],
            call_medians[language],
            deltas_by_language[language],
            ratios_by_language[language],
        )
        if matching != [expected_line]:
            raise ValueError(f"summary.md table row mismatch: {language}")

    print("verified: 9 runs, 900 samples, aggregates, summary, manifest and checksums")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/direct-function-call-comparison"))
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/function-call-analysis/manifest.json"))
    arguments = parser.parse_args()
    verify_public_data(arguments.output_dir, arguments.manifest)
