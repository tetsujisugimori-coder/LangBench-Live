#!/usr/bin/env python3
"""Publish and independently recompute a completed balanced-order series."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

LANGUAGES = ("python", "javascript", "c")
CASES = ("direct", "function_call")
PLAN = ("direct_first", "function_call_first", "function_call_first", "direct_first") * 3


def stats(values: list[float]) -> dict:
    return {"mean_ms": statistics.mean(values), "median_ms": statistics.median(values),
            "sample_sd_ms": statistics.stdev(values), "min_ms": min(values), "max_ms": max(values)}


def analyze(series_file: Path) -> tuple[dict, list[dict]]:
    series = json.loads(series_file.read_text(encoding="utf-8-sig"))
    if tuple(series.get("planned_orders", ())) != PLAN or series.get("requested_runs") != 12:
        raise ValueError("series does not contain the fixed 12-run D,F,F,D plan")
    runs = series.get("runs", [])
    if len(runs) != 12 or series.get("successful_runs") != 12:
        raise ValueError("incomplete series; all 12 original runs are required")
    public_runs, samples = [], []
    seen_ids: set[str] = set()
    for number, run in enumerate(runs, 1):
        expected = PLAN[number - 1]
        if run.get("status") != "success" or run.get("requested_order") != expected or run.get("actual_order") != expected:
            raise ValueError(f"run {number} is failed or has an order mismatch")
        if run["experiment_id"] in seen_ids: raise ValueError("duplicate experiment_id")
        seen_ids.add(run["experiment_id"])
        report = json.loads(Path(run["archive_path"]).with_name(f"run-{number:02d}-samples.json").read_text()) if False else json.loads((series_file.parent / f"run-{number:02d}-samples.json").read_text())
        entries = report["runs"][0]["cases"]
        language_rows = {}
        for language in LANGUAGES:
            case_values = {case: next(e["samples_ms"] for e in entries if e["language"] == language and e["case"] == case) for case in CASES}
            if any(len(values) != 50 for values in case_values.values()): raise ValueError("each case must contain 50 samples")
            computed = {case: stats(values) for case, values in case_values.items()}
            delta = computed["function_call"]["median_ms"] - computed["direct"]["median_ms"]
            denominator = computed["direct"]["median_ms"]
            language_rows[language] = {**computed, "median_delta_ms": delta,
                "median_ratio": None if denominator == 0 else computed["function_call"]["median_ms"] / denominator,
                "sign": "positive" if delta > 0 else "negative" if delta < 0 else "zero"}
            position = {case: pos for pos, case in enumerate(CASES if expected == "direct_first" else reversed(CASES), 1)}
            for case, values in case_values.items():
                samples.extend({"series_id": series["series_id"], "experiment_id": run["experiment_id"],
                    "run_id": report["runs"][0]["archive_id"], "language": language, "block": run["block"],
                    "series_run": number, "requested_order": expected, "actual_order": expected,
                    "case": case, "case_position": position[case], "sample": i, "elapsed_ms": value}
                    for i, value in enumerate(values, 1))
        public_runs.append({"experiment_id": run["experiment_id"], "block": run["block"],
                            "series_run": number, "measurement_order": expected, "languages": language_rows})
    groups = {}
    for language in LANGUAGES:
        groups[language] = {}
        for order in ("direct_first", "function_call_first"):
            values = [r["languages"][language]["median_delta_ms"] for r in public_runs if r["measurement_order"] == order]
            ratios = [r["languages"][language]["median_ratio"] for r in public_runs if r["measurement_order"] == order]
            groups[language][order] = {"run_count": 6, "median_delta_ms": statistics.median(values),
                "delta_range_ms": [min(values), max(values)], "median_ratio": statistics.median(ratios),
                "ratio_range": [min(ratios), max(ratios)],
                "sign_counts": {s: sum((v > 0) - (v < 0) == n for v in values) for s, n in (("positive",1),("zero",0),("negative",-1))}}
    return {"schema_version": "1.0", "series_id": series["series_id"], "statistical_unit": "independent process run",
            "rounding": "JSON preserves calculations; presentation rounds only", "runs": public_runs,
            "order_summaries": groups}, samples


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("series", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args(); payload, samples = analyze(args.series); args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "public-data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output / "public-data.csv").open("w", newline="", encoding="utf-8") as stream:
        columns = ["series_run", "block", "measurement_order", "language", "direct_median_ms", "function_call_median_ms", "median_delta_ms", "median_ratio", "sign"]
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for run in payload["runs"]:
            for language, result in run["languages"].items():
                writer.writerow({"series_run": run["series_run"], "block": run["block"], "measurement_order": run["measurement_order"], "language": language,
                    "direct_median_ms": result["direct"]["median_ms"], "function_call_median_ms": result["function_call"]["median_ms"],
                    "median_delta_ms": result["median_delta_ms"], "median_ratio": result["median_ratio"], "sign": result["sign"]})
    with (args.output / "public-samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=samples[0]); writer.writeheader(); writer.writerows(samples)
    return 0


if __name__ == "__main__": raise SystemExit(main())
