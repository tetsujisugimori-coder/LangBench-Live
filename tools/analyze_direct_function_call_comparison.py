#!/usr/bin/env python3
"""Recalculate public aggregates from ignored, per-experiment raw result JSONs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


LANGUAGES = ("c", "python", "javascript")
FILES = {language: f"function_call_numeric_sum_{language}_result.json" for language in LANGUAGES}
SOURCES = {
    "c": Path("benchmarks/function_call_numeric_sum/c/main.c"),
    "python": Path("benchmarks/function_call_numeric_sum/python/main.py"),
    "javascript": Path("benchmarks/function_call_numeric_sum/javascript/main.js"),
}
CASES = ("direct", "function_call")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded_stats(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    js_round = lambda value, digits: math.floor(value * (10**digits) + 0.5) / (10**digits)
    return {
        "mean_ms": js_round(statistics.mean(samples), 3),
        "median_ms": js_round(statistics.median(samples), 3),
        "sample_sd_ms": js_round(statistics.stdev(samples), 6),
        "min_ms": js_round(min(samples), 3),
        "max_ms": js_round(max(samples), 3),
    }


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(raw_root: Path, manifest_path: Path) -> tuple[dict, list[dict]]:
    manifest = load_manifest(manifest_path)
    repo_root = manifest_path.resolve().parents[2]
    for language, relative_source in SOURCES.items():
        source_bytes = (repo_root / relative_source).read_bytes().replace(b"\r\n", b"\n")
        actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if actual_sha256 != manifest["languages"][language]["condition"]["source_sha256"]:
            raise ValueError(f"current source SHA-256 differs from PR #60 manifest: {relative_source}")
    rows: list[dict] = []
    trial_groups: dict[str, dict] = {}
    for trial_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        trial: dict = {"experiment_id": trial_dir.name, "languages": {}}
        for language in LANGUAGES:
            source = trial_dir / FILES[language]
            result = json.loads(source.read_text(encoding="utf-8"))
            if result.get("experiment_id") != trial_dir.name:
                raise ValueError(f"experiment_id mismatch: {source}")
            if result.get("language") != language or result.get("status") != "success":
                raise ValueError(f"invalid result status/language: {source}")
            if not result.get("validation", {}).get("passed"):
                raise ValueError(f"checksum validation failed: {source}")
            if result["config"] != {
                "item_count": 1_000_000,
                "warmup_iterations": 5,
                "measurement_iterations": 50,
                "numeric_type": "integer",
                "value_field": "value",
                "cases": ["direct", "function_call"],
            }:
                raise ValueError(f"unexpected benchmark configuration: {source}")
            provenance = result["optimization_analysis"]["provenance"]
            expected = manifest["languages"][language]
            if provenance.get("status") != "matched" or provenance.get("matched") is not True:
                raise ValueError(f"analysis provenance is not matched: {source}")
            if provenance.get("artifact_id") != expected["artifact_id"]:
                raise ValueError(f"analysis artifact mismatch: {source}")
            if provenance.get("current") != expected["condition"]:
                raise ValueError(f"runtime condition differs from PR #60 manifest: {source}")
            file_hash = sha256(source)
            case_stats = {}
            for case in CASES:
                samples = result["results"][case]["samples_ms"]
                if len(samples) != 50 or not all(math.isfinite(x) and x >= 0 for x in samples):
                    raise ValueError(f"expected 50 finite samples for {case}: {source}")
                calculated = rounded_stats(samples)
                recorded = result["results"][case]
                if (abs(calculated["mean_ms"] - recorded["mean_ms"]) > 0.001001
                        or abs(calculated["median_ms"] - recorded["median_ms"]) > 0.001001):
                    raise ValueError(f"published mean/median mismatch: {source} {case}")
                case_stats[case] = calculated
            delta = math.floor((case_stats["function_call"]["median_ms"] - case_stats["direct"]["median_ms"]) * 1000 + 0.5) / 1000
            ratio = math.floor(case_stats["function_call"]["median_ms"] / case_stats["direct"]["median_ms"] * 1_000_000 + 0.5) / 1_000_000
            entry = {
                "experiment_id": trial_dir.name,
                "language": language,
                "run_id": result["run_id"],
                "created_at": result["created_at"],
                "raw_sha256": file_hash,
                "source_sha256": provenance["current"]["source_sha256"],
                "implementation": provenance["current"]["implementation"],
                "architecture": provenance["current"]["architecture"],
                "options": provenance["current"]["options"],
                "analysis_artifact_id": provenance["artifact_id"],
                "analysis_findings": expected["findings"],
                "sample_count_per_case": 50,
                "direct": case_stats["direct"],
                "function_call": case_stats["function_call"],
                "median_delta_call_minus_direct_ms": delta,
                "median_ratio_call_over_direct": ratio,
                "checksums": result["validation"],
            }
            trial["languages"][language] = entry
            rows.append(entry)
        trial_groups[trial_dir.name] = trial

    if not trial_groups:
        raise ValueError(f"no raw experiment directories found: {raw_root}")
    summaries = {}
    for language in LANGUAGES:
        entries = [trial["languages"][language] for trial in trial_groups.values()]
        deltas = [entry["median_delta_call_minus_direct_ms"] for entry in entries]
        ratios = [entry["median_ratio_call_over_direct"] for entry in entries]
        summaries[language] = {
            "independent_experiment_count": len(entries),
            "within_run_samples_per_case": 50,
            "median_delta_ms_across_experiments": math.floor(statistics.median(deltas) * 1000 + 0.5) / 1000,
            "median_delta_ms_range": [min(deltas), max(deltas)],
            "median_ratio_across_experiments": math.floor(statistics.median(ratios) * 1_000_000 + 0.5) / 1_000_000,
            "median_ratio_range": [min(ratios), max(ratios)],
        }

    payload = {
        "schema_version": "1.0",
        "title": "同一言語内のdirect／function_call独立測定比較",
        "generated_from": "tools/analyze_direct_function_call_comparison.py",
        "analysis_manifest": "artifacts/function-call-analysis/manifest.json",
        "plan": "artifacts/direct-function-call-comparison/plan.md",
        "data_boundary": {
            "published_contains_raw_samples": False,
            "published_contains_per_experiment_aggregates": True,
            "raw_data_location": "results/diagnostics/issue61-direct-function-call-20260929/results/raw-matched/ (ignored; not committed)",
            "experiment_id_semantics": "IDs use a schema-required timestamp-shaped label chosen before the run; use run_id and created_at as the actual execution time because the ID prefix does not match the recorded clock time.",
            "raw_sha256_published_for_audit": True,
        },
        "statistical_unit": "independent process experiment; the 50 samples per case are within-run observations, not independent experiments",
        "interpretation_limit": "descriptive association only; runtime evidence does not establish optimization causation; no cross-language speed ranking",
        "experiment_count": len(trial_groups),
        "conditions": {
            "item_count": 1_000_000,
            "warmup_iterations": 5,
            "measurement_iterations_per_case": 50,
            "case_order": ["direct", "function_call"],
            "platform": "Windows x64; current machine; one machine only",
        },
        "language_summaries": summaries,
        "experiments": list(trial_groups.values()),
    }
    return payload, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload, rows = analyze(args.raw_dir, args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "public-data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    columns = [
        "experiment_id", "language", "run_id", "created_at", "raw_sha256", "source_sha256",
        "implementation", "architecture", "options", "analysis_artifact_id", "analysis_findings",
        "sample_count_per_case", "direct_mean_ms", "direct_median_ms", "direct_sample_sd_ms",
        "direct_min_ms", "direct_max_ms", "function_call_mean_ms", "function_call_median_ms",
        "function_call_sample_sd_ms", "function_call_min_ms", "function_call_max_ms",
        "median_delta_call_minus_direct_ms", "median_ratio_call_over_direct",
    ]
    with (args.output_dir / "public-data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key) for key in columns if key in row}
            for case in CASES:
                for key, value in row[case].items():
                    flat[f"{case}_{key}"] = value
            flat["implementation"] = row["implementation"]["name"] + " " + row["implementation"]["version"]
            flat["options"] = json.dumps(row["options"], ensure_ascii=False, separators=(",", ":"))
            flat["analysis_findings"] = json.dumps(row["analysis_findings"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow(flat)
    print(f"experiments={len(payload['experiments'])} language_rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
