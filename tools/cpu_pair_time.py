"""Optional, descriptive time observations for CPU pair experiments."""

import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
import json


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except ValueError:
        return None


def load_diagnostics(document, directory):
    """Read only explicitly named per-run files within the experiment directory."""
    result = {}
    root = Path(directory).resolve()
    for run in document.get("runs", []):
        if not isinstance(run, dict):
            continue
        name = run.get("cpu_diagnostic_file")
        if not isinstance(name, str):
            continue
        path = (root / name).resolve()
        if path.parent != root:
            result[name] = {"_load_error": "diagnostic_path_outside_experiment"}
            continue
        try:
            result[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            result[name] = {"_load_error": "diagnostic_file_unreadable"}
    return result


def _busy_observation(run, diagnostic):
    interval = diagnostic.get("requested_interval_ms") if isinstance(diagnostic, dict) else None
    empty = {"status": "insufficient_data", "reason": None, "sample_count": 0,
             "sample_indices": [], "sample_qpc_ranges": [], "monitor_qpc_range": None,
             "run_qpc_range": None, "run_duration_qpc": None,
             "overlap_duration_qpc": None, "overlap_ratio": None,
             "requested_interval_ms": interval if isinstance(interval, int) and not isinstance(interval, bool) and interval > 0 else None,
             "median_cpu_busy_percent": None,
             "mean_cpu_busy_percent": None, "minimum_cpu_busy_percent": None,
             "maximum_cpu_busy_percent": None}
    window = run.get("diagnostic_qpc")
    if isinstance(window, dict):
        start, end, frequency = (window.get(key) for key in ("start_qpc", "end_qpc", "frequency_hz"))
        if (all(isinstance(v, int) and not isinstance(v, bool) for v in (start, end, frequency))
                and start < end and frequency > 0):
            empty["run_qpc_range"] = {"start_qpc": start, "end_qpc": end}
            empty["run_duration_qpc"] = end - start
    if not run.get("cpu_diagnostic_file"):
        empty["reason"] = "diagnostic_file_missing"
        return empty
    if diagnostic is None or not isinstance(diagnostic, dict) or diagnostic.get("_load_error"):
        empty["reason"] = diagnostic.get("_load_error", "diagnostic_file_missing") if isinstance(diagnostic, dict) else "diagnostic_file_missing"
        return empty
    if empty["run_qpc_range"] is None:
        empty["reason"] = "clock_mapping_unavailable"
        return empty
    monitor_start, monitor_end = diagnostic.get("started_qpc"), diagnostic.get("ended_qpc")
    if (diagnostic.get("clock") != "windows_qpc"
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in (monitor_start, monitor_end))
            or diagnostic.get("frequency_hz") != frequency
            or not monitor_start <= start < end <= monitor_end):
        empty["reason"] = "clock_mapping_unavailable"
        return empty
    empty["monitor_qpc_range"] = {"start_qpc": monitor_start, "end_qpc": monitor_end}
    empty["overlap_duration_qpc"] = 0
    empty["overlap_ratio"] = 0.0
    samples = diagnostic.get("observations")
    if not isinstance(samples, list) or not samples:
        empty["reason"] = "diagnostic_samples_missing"
        return empty
    values = []
    overlaps = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            continue
        a, b, busy = (sample.get(key) for key in ("start_qpc", "end_qpc", "cpu_busy_percent"))
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (a, b)) or a >= b:
            continue
        if max(start, a) >= min(end, b):
            continue
        if isinstance(busy, (int, float)) and not isinstance(busy, bool) and math.isfinite(busy) and 0 <= busy <= 100:
            values.append(float(busy))
            empty["sample_indices"].append(index)
            empty["sample_qpc_ranges"].append({"start_qpc": a, "end_qpc": b})
            overlaps.append((max(start, a), min(end, b)))
    if not values:
        empty["reason"] = "no_overlapping_valid_samples"
        return empty
    merged = []
    for left, right in sorted(overlaps):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    overlap_duration = sum(right - left for left, right in merged)
    empty["overlap_duration_qpc"] = min(overlap_duration, empty["run_duration_qpc"])
    empty["overlap_ratio"] = empty["overlap_duration_qpc"] / empty["run_duration_qpc"]
    empty.update(status="available", sample_count=len(values), median_cpu_busy_percent=statistics.median(values),
                 mean_cpu_busy_percent=statistics.mean(values), minimum_cpu_busy_percent=min(values),
                 maximum_cpu_busy_percent=max(values))
    return empty


def analyze_time(document, cycle_pairs, diagnostics=None):
    diagnostics = diagnostics or {}
    origin = timestamp(document.get("started_at"))
    observations = []
    balanced = document.get("measurement_settings", {}).get("pair_run_order") == "balanced ABBA rounds" if isinstance(document.get("measurement_settings"), dict) else False
    for index, run in enumerate(document.get("runs", [])):
        if (not isinstance(run, dict) or run.get("status") != "success"
                or run.get("comparison_cpu") not in ("A", "B")
                or not isinstance(run.get("cycle"), int) or isinstance(run.get("cycle"), bool)
                or run["cycle"] < 1):
            continue
        started, ended = timestamp(run.get("started_at")), timestamp(run.get("ended_at"))
        elapsed = (started - origin).total_seconds() if started and origin else None
        duration = (ended - started).total_seconds() if started and ended and ended >= started else None
        name = run.get("cpu_diagnostic_file")
        busy = _busy_observation(run, diagnostics.get(name) if isinstance(name, str) else None)
        cycle = run.get("cycle")
        expected_order = (("A_then_B", "B_then_A", "B_then_A", "A_then_B")[(cycle - 1) % 4]
                          if balanced and isinstance(cycle, int) and cycle > 0 else "A_then_B")
        order = run.get("execution_order", expected_order)
        inferred_position = (1 if run["comparison_cpu"] == order[0] else 2) if order in ("A_then_B", "B_then_A") else None
        if not started or not ended or duration is None or elapsed is None or elapsed < 0:
            timing_reason = "invalid_or_missing_timestamp"
            elapsed = None
        else:
            timing_reason = None
        observations.append({"run_number": run.get("run_number", index + 1), "cycle": cycle,
                             "run_id": run.get("run_id"), "comparison_cpu": run["comparison_cpu"],
                             "execution_order": order,
                             "position": run.get("position", inferred_position), "started_at": run.get("started_at"),
                             "ended_at": run.get("ended_at"), "median_ms": run.get("median_ms"),
                             "elapsed_since_experiment_start_seconds": elapsed,
                             "run_wall_duration_seconds": duration, "timing_reason": timing_reason,
                             "cpu_diagnostic_file": name, "diagnostic_qpc": run.get("diagnostic_qpc"),
                             "diagnostic_match_method": "strict overlap of run QPC interval and CPU sample QPC interval; unweighted sample statistics",
                             "cpu_busy": busy})
    observations.sort(key=lambda row: (timestamp(row["started_at"]) or datetime.max.replace(tzinfo=timezone.utc), row["run_number"] if isinstance(row["run_number"], int) else 0))
    by_key = {(row["cycle"], row["comparison_cpu"]): row for row in observations}
    trend = []
    for pair in cycle_pairs:
        a, b = (by_key.get((pair["cycle"], side)) for side in ("A", "B"))
        starts = [row["elapsed_since_experiment_start_seconds"] for row in (a, b) if row and row["elapsed_since_experiment_start_seconds"] is not None]
        gap = abs((timestamp(a["started_at"]) - timestamp(b["started_at"])).total_seconds()) if a and b and timestamp(a["started_at"]) and timestamp(b["started_at"]) else None
        trend.append({"cycle": pair["cycle"], "execution_order": pair["execution_order"],
                      "cpu_a_median_ms": pair["cpu_a_median_ms"], "cpu_b_median_ms": pair["cpu_b_median_ms"],
                      "b_minus_a_ms": pair["b_minus_a_ms"],
                      "elapsed_since_experiment_start_seconds": min(starts) if starts else None,
                      "a_b_start_gap_seconds": gap,
                      "cpu_a_busy": a["cpu_busy"] if a else None, "cpu_b_busy": b["cpu_busy"] if b else None})
    # Split whole cycles so both CPU identities occur in each half.
    cycles = sorted(row["cycle"] for row in trend)
    midpoint = len(cycles) // 2
    early, late = set(cycles[:midpoint]), set(cycles[midpoint:])
    comparison = {"status": "insufficient_data", "reason": None,
                  "split_method": "first and last halves of complete cycles",
                  "early_cycles": sorted(early), "late_cycles": sorted(late), "by_cpu": {},
                  "order_counts": {half: {order: sum(row["execution_order"] == order and row["cycle"] in subset for row in trend)
                                          for order in ("A_then_B", "B_then_A")}
                                   for half, subset in (("early", early), ("late", late))}}
    for side in ("A", "B"):
        first = [row["median_ms"] for row in observations if row["comparison_cpu"] == side and row["cycle"] in early and isinstance(row["median_ms"], (int, float))]
        second = [row["median_ms"] for row in observations if row["comparison_cpu"] == side and row["cycle"] in late and isinstance(row["median_ms"], (int, float))]
        comparison["by_cpu"][side] = {"early_run_count": len(first), "late_run_count": len(second),
                                      "early_median_ms": statistics.median(first) if first else None,
                                      "late_median_ms": statistics.median(second) if second else None,
                                      "late_minus_early_ms": statistics.median(second) - statistics.median(first) if first and second else None}
    if len(early) < 2 or len(late) < 2:
        comparison["reason"] = "insufficient_complete_cycles"
    elif any(comparison["by_cpu"][side][f"{half}_run_count"] < 2 for side in ("A", "B") for half in ("early", "late")):
        comparison["reason"] = "insufficient_runs_per_cpu"
    elif comparison["order_counts"]["early"] != comparison["order_counts"]["late"]:
        comparison["reason"] = "unequal_order_counts"
    elif any(row["elapsed_since_experiment_start_seconds"] is None for row in observations if row["cycle"] in early | late):
        comparison["reason"] = "timing_data_missing"
    else:
        comparison["status"] = "available"
    covered = [row for row in observations if row["cpu_busy"]["status"] == "available"]
    run_busy_medians = [row["cpu_busy"]["median_cpu_busy_percent"] for row in covered]
    sample_counts = [row["cpu_busy"]["sample_count"] for row in covered]
    overlap_ratios = [row["cpu_busy"]["overlap_ratio"] for row in covered]
    timed = [row for row in observations if row["elapsed_since_experiment_start_seconds"] is not None]
    reasons = sorted({row["cpu_busy"]["reason"] for row in observations if row["cpu_busy"]["reason"]} |
                     {row["timing_reason"] for row in observations if row["timing_reason"]})
    elapsed_total = (timestamp(document.get("ended_at")) - origin).total_seconds() if origin and timestamp(document.get("ended_at")) else None
    return {"status": "available" if any(row in covered for row in timed) else "insufficient_data", "reasons": reasons,
            "experiment_elapsed_seconds": elapsed_total if elapsed_total is not None and elapsed_total >= 0 else None,
            "successful_run_count": len(observations), "runs_with_diagnostic_coverage": len(covered),
            "diagnostic_density": {
                "covered_run_count": len(covered), "successful_run_count": len(observations),
                "sample_count_per_covered_run": {"minimum": min(sample_counts) if sample_counts else None,
                                                 "median": statistics.median(sample_counts) if sample_counts else None,
                                                 "maximum": max(sample_counts) if sample_counts else None},
                "overlap_ratio_per_covered_run": {"minimum": min(overlap_ratios) if overlap_ratios else None,
                                                  "median": statistics.median(overlap_ratios) if overlap_ratios else None,
                                                  "maximum": max(overlap_ratios) if overlap_ratios else None}},
            "cpu_busy_run_median_statistics": {"run_count": len(run_busy_medians),
                "median_percent": statistics.median(run_busy_medians) if run_busy_medians else None,
                "minimum_percent": min(run_busy_medians) if run_busy_medians else None,
                "maximum_percent": max(run_busy_medians) if run_busy_medians else None},
            "run_time_observations": observations, "run_sequence": observations,
            "early_late_comparison": comparison, "cycle_trend": trend,
            "interpretation": "Descriptive observations only; time and CPU busy associations do not establish causes."}
