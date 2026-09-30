#!/usr/bin/env python3
"""Validate and publish a completed Issue #66 balanced-order series."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

LANGUAGES = ("python", "javascript", "c")
CASES = ("direct", "function_call")
PLAN = ("direct_first", "function_call_first", "function_call_first", "direct_first") * 3
CSV_COLUMNS = ("series_run", "block", "measurement_order", "language",
               "direct_mean_ms", "direct_median_ms", "direct_sample_sd_ms", "direct_min_ms", "direct_max_ms",
               "function_call_mean_ms", "function_call_median_ms", "function_call_sample_sd_ms",
               "function_call_min_ms", "function_call_max_ms", "median_delta_ms", "median_ratio", "sign")


def stats(values: list[float]) -> dict[str, float]:
    return {"mean_ms": statistics.mean(values), "median_ms": statistics.median(values),
            "sample_sd_ms": statistics.stdev(values), "min_ms": min(values), "max_ms": max(values)}


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [run["median_delta_ms"] for run in runs]
    ratios = [run["median_ratio"] for run in runs if run["median_ratio"] is not None]
    return {"run_count": len(runs), "median_delta_ms": statistics.median(deltas),
            "delta_range_ms": [min(deltas), max(deltas)],
            "median_ratio": statistics.median(ratios) if ratios else None,
            "ratio_range": [min(ratios), max(ratios)] if ratios else None,
            "null_ratio_count": len(runs) - len(ratios),
            "sign_counts": {sign: sum(run["sign"] == sign for run in runs)
                            for sign in ("positive", "negative", "zero")}}


def analyze(series_file: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    series = json.loads(series_file.read_text(encoding="utf-8-sig"))
    required_provenance = ("series_id", "git_head", "input_sha256", "host")
    if any(not series.get(key) for key in required_provenance):
        raise ValueError("series provenance is incomplete")
    if tuple(series.get("planned_orders", ())) != PLAN or series.get("requested_runs") != 12:
        raise ValueError("series does not contain the fixed 12-run D,F,F,D plan")
    runs = series.get("runs", [])
    if len(runs) != 12 or series.get("successful_runs") != 12:
        raise ValueError("incomplete series; all 12 original runs are required")
    public_runs: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    seen_experiments: set[str] = set()
    seen_archives: set[str] = set()
    for number, run in enumerate(runs, 1):
        expected_order, expected_block = PLAN[number - 1], (number - 1) // 4 + 1
        if (run.get("order") != number or run.get("block") != expected_block or run.get("status") != "success"
                or run.get("requested_order") != expected_order or run.get("actual_order") != expected_order):
            raise ValueError(f"run {number} identity, block, status, or order differs from the fixed plan")
        experiment_id, archive_id = run.get("experiment_id"), run.get("archive_id")
        if not experiment_id or experiment_id in seen_experiments or not archive_id or archive_id in seen_archives:
            raise ValueError(f"run {number} has a missing or duplicate experiment/archive ID")
        seen_experiments.add(experiment_id); seen_archives.add(archive_id)
        report = json.loads((series_file.parent / f"run-{number:02d}-samples.json").read_text(encoding="utf-8"))
        report_runs = report.get("runs")
        if not isinstance(report_runs, list) or len(report_runs) != 1:
            raise ValueError(f"run {number} sample report must contain exactly one run")
        report_run = report_runs[0]
        if report_run.get("experiment_id") != experiment_id or report_run.get("archive_id") != archive_id:
            raise ValueError(f"run {number} sample report identity mismatch")
        run_ids = report_run.get("run_ids")
        if not isinstance(run_ids, dict) or set(run_ids) != set(LANGUAGES) or any(not value for value in run_ids.values()):
            raise ValueError(f"run {number} sample report run IDs are incomplete")
        entries = report_run.get("cases")
        if not isinstance(entries, list) or len(entries) != len(LANGUAGES) * len(CASES):
            raise ValueError(f"run {number} must contain exactly one entry per language/case")
        indexed: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in entries:
            key = (entry.get("language"), entry.get("case"))
            if key not in {(language, case) for language in LANGUAGES for case in CASES} or key in indexed:
                raise ValueError(f"run {number} contains an unknown or duplicate language/case")
            indexed[key] = entry
        language_rows = {}
        measured_cases = CASES if expected_order == "direct_first" else tuple(reversed(CASES))
        positions = {case: position for position, case in enumerate(measured_cases, 1)}
        for language in LANGUAGES:
            case_values = {case: indexed[(language, case)].get("samples_ms") for case in CASES}
            if any(not isinstance(values, list) or len(values) != 50 or
                   any(type(value) not in (int, float) or value < 0 for value in values)
                   for values in case_values.values()):
                raise ValueError(f"run {number}/{language} requires 50 nonnegative numeric samples per case")
            computed = {case: stats(values) for case, values in case_values.items()}
            delta = computed["function_call"]["median_ms"] - computed["direct"]["median_ms"]
            denominator = computed["direct"]["median_ms"]
            language_rows[language] = {**computed, "median_delta_ms": delta,
                "median_ratio": None if denominator == 0 else computed["function_call"]["median_ms"] / denominator,
                "sign": "positive" if delta > 0 else "negative" if delta < 0 else "zero"}
            for case, values in case_values.items():
                samples.extend({"series_id": series["series_id"], "experiment_id": experiment_id,
                    "archive_id": archive_id, "run_id": run_ids[language], "language": language, "block": expected_block,
                    "series_run": number, "requested_order": expected_order, "actual_order": expected_order,
                    "case": case, "case_position": positions[case], "sample": index, "elapsed_ms": value}
                    for index, value in enumerate(values, 1))
        public_runs.append({"experiment_id": experiment_id, "archive_id": archive_id, "run_ids": run_ids, "block": expected_block,
                            "series_run": number, "measurement_order": expected_order, "languages": language_rows})
    order_summaries, block_summaries = {}, {}
    for language in LANGUAGES:
        order_summaries[language] = {order: aggregate([run["languages"][language] for run in public_runs
                                                       if run["measurement_order"] == order])
                                     for order in ("direct_first", "function_call_first")}
        block_summaries[language] = {str(block): aggregate([run["languages"][language] for run in public_runs
                                                            if run["block"] == block]) for block in range(1, 4)}
    provenance = {key: series[key] for key in required_provenance}
    return {"schema_version": "2.0", "benchmark": "function_call_numeric_sum", "provenance": provenance,
            "plan": list(PLAN), "statistical_unit": "independent process run",
            "rounding": "stored values are unrounded; sign is classified before presentation rounding",
            "runs": public_runs, "order_summaries": order_summaries, "block_summaries": block_summaries}, samples


def csv_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in payload["runs"]:
        for language in LANGUAGES:
            result = run["languages"][language]
            row = {"series_run": run["series_run"], "block": run["block"],
                   "measurement_order": run["measurement_order"], "language": language,
                   "median_delta_ms": result["median_delta_ms"], "median_ratio": result["median_ratio"],
                   "sign": result["sign"]}
            for case in CASES:
                row.update({f"{case}_{key}": value for key, value in result[case].items()})
            rows.append(row)
    return rows


def manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    provenance = payload["provenance"]
    return {"schema_version": "2.0", "issue": 66, "benchmark": payload["benchmark"], "status": "completed",
            "plan": payload["plan"], "blocks": 3, "runs_per_language": 12, "samples_per_case": 50,
            "expected_public_samples": 3600, "language_execution_order": list(LANGUAGES),
            "measurement_git_sha": provenance["git_head"], "series_id": provenance["series_id"],
            "input_sha256": provenance["input_sha256"], "host": provenance["host"]}


def summary_text(payload: dict[str, Any]) -> str:
    provenance = payload["provenance"]
    return ("# 均衡順序測定\n\n"
            f"series ID: `{provenance['series_id']}`  \n"
            f"測定Git SHA: `{provenance['git_head']}`  \n"
            "固定したD,F,F,D×3の12 run（3言語、各case 50 sample）を完了しました。"
            "数値はpublic-samples.csvから検算し、詳細はpublic-data.json / CSVに保存しています。\n")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("series", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args(); payload, samples = analyze(args.series); args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "public-data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output / "public-data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS); writer.writeheader(); writer.writerows(csv_rows(payload))
    with (args.output / "public-samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=samples[0]); writer.writeheader(); writer.writerows(samples)
    (args.output / "manifest.json").write_text(json.dumps(manifest_payload(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "summary.md").write_text(summary_text(payload), encoding="utf-8")
    print(f"series={payload['provenance']['series_id']} runs=12 samples={len(samples)}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
