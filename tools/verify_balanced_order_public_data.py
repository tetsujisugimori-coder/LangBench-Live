#!/usr/bin/env python3
"""Recalculate every Issue #66 publication value solely from public-samples.csv."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

if __package__:
    from .analyze_balanced_order import summary_table_lines
else:
    from analyze_balanced_order import summary_table_lines

LANGUAGES = ("python", "javascript", "c")
CASES = ("direct", "function_call")
PLAN = ("direct_first", "function_call_first", "function_call_first", "direct_first") * 3
STAT_KEYS = ("mean_ms", "median_ms", "sample_sd_ms", "min_ms", "max_ms")


def stats(values: list[float]) -> dict[str, float]:
    return {"mean_ms": statistics.mean(values), "median_ms": statistics.median(values),
            "sample_sd_ms": statistics.stdev(values), "min_ms": min(values), "max_ms": max(values)}


def same(expected: Any, actual: Any, location: str) -> None:
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        if math.isfinite(expected) and math.isfinite(actual) and expected == actual: return
    elif expected == actual: return
    raise ValueError(f"published value mismatch at {location}: expected {expected!r}, got {actual!r}")


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [item["median_delta_ms"] for item in results]
    ratios = [item["median_ratio"] for item in results if item["median_ratio"] is not None]
    return {"run_count": len(results), "median_delta_ms": statistics.median(deltas),
            "delta_range_ms": [min(deltas), max(deltas)],
            "median_ratio": statistics.median(ratios) if ratios else None,
            "ratio_range": [min(ratios), max(ratios)] if ratios else None,
            "null_ratio_count": len(results) - len(ratios),
            "sign_counts": {sign: sum(item["sign"] == sign for item in results)
                            for sign in ("positive", "negative", "zero")}}


def verify(root: Path) -> None:
    data = json.loads((root / "public-data.json").read_text(encoding="utf-8"))
    with (root / "public-samples.csv").open(newline="", encoding="utf-8") as stream:
        sample_rows = list(csv.DictReader(stream))
    if len(sample_rows) != 3600: raise ValueError("expected exactly 3,600 public samples")
    series_ids = {row["series_id"] for row in sample_rows}
    if len(series_ids) != 1 or next(iter(series_ids)) != data.get("provenance", {}).get("series_id"):
        raise ValueError("sample series_id does not match public provenance")
    indexed: dict[tuple[int, str, str, int], float] = {}
    identity: dict[int, tuple[str, str]] = {}
    run_ids: dict[tuple[int, str], str] = {}
    for row in sample_rows:
        try:
            run, block, position, sample = (int(row[key]) for key in ("series_run", "block", "case_position", "sample"))
            language, case = row["language"], row["case"]
            value = float(row["elapsed_ms"])
        except (KeyError, ValueError) as error: raise ValueError("invalid public sample field") from error
        if run not in range(1, 13) or block != (run - 1) // 4 + 1 or language not in LANGUAGES or case not in CASES:
            raise ValueError("sample run/block/language/case is outside the fixed plan")
        expected_order = PLAN[run - 1]
        expected_position = (1 if case == "direct" else 2) if expected_order == "direct_first" else (2 if case == "direct" else 1)
        if (row["requested_order"] != expected_order or row["actual_order"] != expected_order
                or position != expected_position or sample not in range(1, 51) or not math.isfinite(value) or value < 0):
            raise ValueError("sample order, position, number, or elapsed value is invalid")
        key = (run, language, case, sample)
        if key in indexed: raise ValueError("duplicate public sample identity")
        indexed[key] = value
        current_identity = (row["experiment_id"], row["archive_id"])
        if run in identity and identity[run] != current_identity: raise ValueError("run identity changes within public samples")
        identity[run] = current_identity
        run_key = (run, language)
        if run_key in run_ids and run_ids[run_key] != row["run_id"]: raise ValueError("language run_id changes within public samples")
        if not row["run_id"]: raise ValueError("empty language run_id")
        run_ids[run_key] = row["run_id"]
    expected_keys = {(run, language, case, sample) for run in range(1, 13) for language in LANGUAGES
                     for case in CASES for sample in range(1, 51)}
    if set(indexed) != expected_keys or len(identity) != 12: raise ValueError("public sample identities contain gaps")
    published_runs = data.get("runs")
    if not isinstance(published_runs, list) or len(published_runs) != 12: raise ValueError("public-data must contain 12 runs")
    recalculated: dict[tuple[int, str], dict[str, Any]] = {}
    for run in range(1, 13):
        published = published_runs[run - 1]
        experiment_id, archive_id = identity[run]
        expected_run = {"experiment_id": experiment_id, "archive_id": archive_id,
                        "run_ids": {language: run_ids[(run, language)] for language in LANGUAGES}, "block": (run - 1) // 4 + 1,
                        "series_run": run, "measurement_order": PLAN[run - 1]}
        for key, value in expected_run.items(): same(value, published.get(key), f"runs[{run}].{key}")
        if set(published.get("languages", {})) != set(LANGUAGES): raise ValueError("published language set mismatch")
        for language in LANGUAGES:
            result = {case: stats([indexed[(run, language, case, sample)] for sample in range(1, 51)]) for case in CASES}
            delta = result["function_call"]["median_ms"] - result["direct"]["median_ms"]
            result.update({"median_delta_ms": delta,
                           "median_ratio": None if result["direct"]["median_ms"] == 0 else result["function_call"]["median_ms"] / result["direct"]["median_ms"],
                           "sign": "positive" if delta > 0 else "negative" if delta < 0 else "zero"})
            recalculated[(run, language)] = result
            same(result, published["languages"][language], f"runs[{run}].languages.{language}")
    expected_orders = {language: {order: aggregate([recalculated[(run, language)] for run in range(1, 13)
                                                  if PLAN[run - 1] == order])
                                  for order in ("direct_first", "function_call_first")} for language in LANGUAGES}
    expected_blocks = {language: {str(block): aggregate([recalculated[(run, language)] for run in range(1, 13)
                                                          if (run - 1) // 4 + 1 == block]) for block in range(1, 4)}
                       for language in LANGUAGES}
    same(expected_orders, data.get("order_summaries"), "order_summaries")
    same(expected_blocks, data.get("block_summaries"), "block_summaries")
    with (root / "public-data.csv").open(newline="", encoding="utf-8") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != 36: raise ValueError("public-data.csv must contain exactly 36 rows")
    seen_csv: set[tuple[int, str]] = set()
    for row in csv_rows:
        key = (int(row["series_run"]), row["language"])
        if key in seen_csv or key not in recalculated: raise ValueError("duplicate or unknown public-data.csv row")
        seen_csv.add(key); run, language = key; result = recalculated[key]
        same(str((run - 1) // 4 + 1), row["block"], "csv.block"); same(PLAN[run - 1], row["measurement_order"], "csv.order")
        for case in CASES:
            for stat in STAT_KEYS: same(result[case][stat], float(row[f"{case}_{stat}"]), f"csv.{case}_{stat}")
        same(result["median_delta_ms"], float(row["median_delta_ms"]), "csv.delta")
        ratio = None if row["median_ratio"] == "" else float(row["median_ratio"])
        same(result["median_ratio"], ratio, "csv.ratio"); same(result["sign"], row["sign"], "csv.sign")
    if seen_csv != set(recalculated): raise ValueError("public-data.csv rows are missing")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("status") != "completed" or manifest.get("series_id") != next(iter(series_ids))
            or manifest.get("measurement_git_sha") != data["provenance"].get("git_head")
            or manifest.get("input_sha256") != data["provenance"].get("input_sha256")
            or manifest.get("host") != data["provenance"].get("host") or manifest.get("plan") != list(PLAN)):
        raise ValueError("manifest does not correspond to public data")
    summary_bytes = (root / "summary.md").read_bytes()
    if summary_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("summary must be UTF-8 without BOM")
    summary_lines = summary_bytes.decode("utf-8").splitlines()
    if any(line != line.rstrip() for line in summary_lines):
        raise ValueError("summary contains trailing whitespace")
    if (f"- series ID: `{manifest['series_id']}`" not in summary_lines
            or f"- 測定Git SHA: `{manifest['measurement_git_sha']}`" not in summary_lines):
        raise ValueError("summary does not identify the published series and measurement SHA")
    # Values come only from public-samples.csv, never the published aggregates.
    # Share display rounding/layout, but not the analyzer's statistical calculation.
    same(summary_table_lines(expected_orders),
         [line for line in summary_lines if line.startswith("|")], "summary principal values")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("root", type=Path); args = parser.parse_args()
    verify(args.root); print("balanced-order public data verified: 12 runs, 36 language runs, 3600 samples")
    return 0


if __name__ == "__main__": raise SystemExit(main())
