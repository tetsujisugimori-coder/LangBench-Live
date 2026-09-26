"""Read-only descriptive analysis for saved CPU topology pair experiments."""

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = "1.0"
LIMITATIONS = [
    "CPU A is always measured before CPU B within each cycle.",
    "CPU identity effects cannot be separated from order/time effects in this experiment design.",
    "Boost state, thermal state, cache state, and background load may contribute to observed differences.",
]
REQUIRED_CPU_FIELDS = ("group_id", "processor_number", "physical_core_id", "efficiency_class")


class InputError(ValueError):
    """Input cannot be read as a CPU pair experiment."""


def load_runs(path: Path) -> dict:
    if path.is_dir():
        path = path / "runs.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
        raise InputError("runs.json must be an object containing a runs array")
    return document


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _stats(values: list[float]) -> dict:
    return {
        "successful_run_count": len(values),
        "median_of_run_medians_ms": statistics.median(values) if values else None,
        "minimum_run_median_ms": min(values) if values else None,
        "maximum_run_median_ms": max(values) if values else None,
        "range_of_run_medians_ms": max(values) - min(values) if values else None,
        "mean_run_median_ms": statistics.mean(values) if values else None,
        "standard_deviation_run_medians_ms": statistics.stdev(values) if len(values) > 1 else None,
        "standard_deviation_kind": "sample; null when fewer than 2 successful runs",
        "run_medians_ms": values,
    }


def _metadata_errors(comparison):
    errors = []
    if not isinstance(comparison, dict):
        return ["comparison metadata is missing or invalid"]
    if comparison.get("candidate_type") not in {
        "same_core_siblings", "same_efficiency_class_different_core", "different_efficiency_class"
    }:
        errors.append("candidate type is missing or unsupported")
    for side in ("cpu_a", "cpu_b"):
        cpu = comparison.get(side)
        if not isinstance(cpu, dict) or any(key not in cpu for key in REQUIRED_CPU_FIELDS):
            errors.append(f"{side.upper()} metadata is missing required CPU identity/topology fields")
    if all(isinstance(comparison.get(side), dict) for side in ("cpu_a", "cpu_b")):
        a, b = comparison["cpu_a"], comparison["cpu_b"]
        if (a.get("group_id"), a.get("processor_number")) == (b.get("group_id"), b.get("processor_number")):
            errors.append("CPU A and CPU B are the same logical CPU")
    if not isinstance(comparison.get("topology_sha256"), str) or not comparison["topology_sha256"]:
        errors.append("topology SHA-256 is missing")
    return errors


def analyze(document: dict, source_file: str = "runs.json", analyzed_at: str | None = None) -> dict:
    errors = _metadata_errors(document.get("comparison"))
    warnings = []
    settings = document.get("measurement_settings")
    if not isinstance(settings, dict):
        errors.append("measurement_settings is missing or invalid")
        settings = {}
    else:
        for key in ("benchmark_identifier", "case", "item_count", "warmup_iterations", "measurement_iterations", "measurement_order", "compiler_options", "pair_run_order"):
            if key not in settings:
                errors.append(f"measurement_settings.{key} is missing")
        if settings.get("pair_run_order") != "CPU A then CPU B, repeated":
            errors.append("measurement order metadata does not declare the expected fixed A-then-B order")

    runs = document["runs"]
    if not runs:
        errors.append("runs array is empty")
    comparison = document.get("comparison") if isinstance(document.get("comparison"), dict) else {}
    cpu_stats = {"A": [], "B": []}
    by_cycle = {}
    statuses = {"failed": 0, "pending": 0, "other": 0}
    hashes = set()
    configs = []
    benchmark_ids, cases, compiler_options = set(), set(), set()
    orders = set()
    run_keys = set()
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            errors.append(f"run at index {index} is not an object")
            continue
        label, cycle = run.get("comparison_cpu"), run.get("cycle")
        if label not in ("A", "B"):
            errors.append(f"run at index {index} has invalid or missing comparison_cpu")
            continue
        if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
            errors.append(f"run at index {index} has invalid cycle number")
            continue
        key = (cycle, label)
        if key in run_keys:
            errors.append(f"cycle {cycle} contains duplicate CPU {label} runs")
        run_keys.add(key)
        by_cycle.setdefault(cycle, {})[label] = run
        expected_position = 1 if label == "A" else 2
        if run.get("position") != expected_position:
            errors.append(f"cycle {cycle} CPU {label} run position does not match the planned A-then-B order")
        if document.get("experiment_id") is not None and run.get("experiment_id") != document["experiment_id"]:
            errors.append(f"run {run.get('run_id', index)} experiment ID disagrees with runs.json")
        if run.get("status") == "failed":
            statuses["failed"] += 1
        elif run.get("status") == "pending":
            statuses["pending"] += 1
        elif run.get("status") == "success":
            median = run.get("median_ms")
            if not _finite_number(median) or median < 0:
                errors.append(f"successful run {run.get('run_id', index)} has invalid median_ms")
            else:
                cpu_stats[label].append((cycle, float(median)))
        else:
            statuses["other"] += 1
            errors.append(f"run {run.get('run_id', index)} has missing or unsupported status")
        binary_hash = run.get("binary_sha256")
        if binary_hash is not None:
            hashes.add(binary_hash)
        configs.append(run.get("benchmark_config"))
        # In this saved format, document.benchmark is the benchmark identifier
        # and each run.benchmark is its case label (for example C/direct).
        benchmark_ids.add(json.dumps(document.get("benchmark"), sort_keys=True))
        cases.add(json.dumps(run.get("benchmark"), sort_keys=True))
        raw_options = run.get("compiler_options", document.get("compiler_options", [])) or []
        compiler_options.add(json.dumps(raw_options, sort_keys=True))
        raw_order = run.get("scheduled_order", [])
        orders.add(tuple(raw_order) if isinstance(raw_order, list) and all(isinstance(v, str) for v in raw_order) else ())
        config = run.get("benchmark_config")
        if isinstance(config, dict):
            for config_key in ("item_count", "warmup_iterations", "measurement_iterations"):
                if config.get(config_key) != settings.get(config_key):
                    errors.append(f"run {run.get('run_id', index)} benchmark config {config_key} disagrees with measurement settings")
        cpu = comparison.get(f"cpu_{label.lower()}")
        if isinstance(cpu, dict):
            if run.get("logical_cpu") != cpu.get("processor_number") or run.get("processor_group_id") != cpu.get("group_id"):
                errors.append(f"run {run.get('run_id', index)} CPU identity disagrees with CPU {label} metadata")
        if run.get("status") == "success" and (not isinstance(binary_hash, str) or not binary_hash):
            errors.append(f"successful run {run.get('run_id', index)} has no binary SHA-256")

    if len(hashes) > 1 or (runs and len(hashes) != 1):
        errors.append("binary SHA-256 is missing or inconsistent across runs")
    if len({json.dumps(config, sort_keys=True) for config in configs}) > 1 or any(not isinstance(c, dict) for c in configs):
        errors.append("benchmark config is missing or inconsistent across runs")
    if len(benchmark_ids) > 1 or "null" in benchmark_ids or (benchmark_ids and json.dumps(settings.get("benchmark_identifier"), sort_keys=True) not in benchmark_ids):
        errors.append("benchmark identifier is missing or inconsistent with measurement settings")
    if len(cases) > 1 or "null" in cases or (cases and json.dumps(settings.get("case"), sort_keys=True) not in cases):
        errors.append("benchmark case is missing or inconsistent with measurement settings")
    if document.get("case") is not None and document.get("case") != settings.get("case"):
        errors.append("top-level benchmark case disagrees with measurement settings")
    if len(compiler_options) > 1 or (compiler_options and json.dumps(settings.get("compiler_options", []), sort_keys=True) not in compiler_options):
        errors.append("compiler options are missing or inconsistent across runs/settings")
    if len(orders) > 1 or (orders and any(order != ("cpu_a", "cpu_b") for order in orders)):
        errors.append("scheduled comparison order is missing, inconsistent, or not CPU A then CPU B")
    if len(runs) % 2:
        warnings.append("run count is odd; at least one comparison cycle is incomplete")
    for cycle, sides in sorted(by_cycle.items()):
        if set(sides) != {"A", "B"}:
            errors.append(f"cycle {cycle} is missing CPU {'B' if 'A' in sides else 'A'} run")
    if statuses["failed"]:
        errors.append(f"{statuses['failed']} failed run(s) are present")
    if statuses["pending"]:
        errors.append(f"{statuses['pending']} pending run(s) are present")
    if statuses["other"]:
        errors.append(f"{statuses['other']} run(s) have unsupported status")

    pairs = []
    differences, ratios = [], []
    for cycle, sides in sorted(by_cycle.items()):
        if set(sides) != {"A", "B"}:
            continue
        a, b = sides["A"].get("median_ms"), sides["B"].get("median_ms")
        if not (_finite_number(a) and _finite_number(b)) or sides["A"].get("status") != "success" or sides["B"].get("status") != "success":
            continue
        diff = float(b) - float(a)
        ratio = float(b) / float(a) if float(a) != 0 else None
        pct = diff / float(a) * 100 if float(a) != 0 else None
        if ratio is not None and not math.isfinite(ratio):
            ratio = None
        if pct is not None and not math.isfinite(pct):
            pct = None
        pairs.append({"cycle": cycle, "cpu_a_median_ms": a, "cpu_b_median_ms": b,
                      "b_minus_a_ms": diff, "b_over_a_ratio": ratio,
                      "b_minus_a_percent_of_a": pct})
        differences.append(diff)
        if ratio is not None:
            ratios.append(ratio)
    all_cycles = sorted(by_cycle)
    expected_count = settings.get("runs_per_cpu")
    if isinstance(expected_count, int) and not isinstance(expected_count, bool) and expected_count > 0 and all_cycles != list(range(1, expected_count + 1)):
        errors.append("observed cycles do not match planned runs_per_cpu")
    metadata = {}
    for label in ("A", "B"):
        cpu = comparison.get(f"cpu_{label.lower()}")
        metadata[label] = ({key: cpu.get(key) for key in REQUIRED_CPU_FIELDS} if isinstance(cpu, dict) else None)
    if isinstance(metadata["A"], dict) and isinstance(metadata["B"], dict):
        a, b = metadata["A"], metadata["B"]
        same_group = a["group_id"] == b["group_id"]
        same_core = same_group and a["physical_core_id"] == b["physical_core_id"]
        same_efficiency = a["efficiency_class"] == b["efficiency_class"]
    else:
        same_group = same_core = same_efficiency = None
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": document.get("experiment_id"),
        "analyzed_at": analyzed_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_file": source_file,
        "analysis_valid": not errors,
        "validation_errors": list(dict.fromkeys(errors)),
        "validation_warnings": warnings,
        "comparison": {"candidate_type": comparison.get("candidate_type"), "selection_reason": comparison.get("selection_reason"),
                       "cpu_a": metadata["A"], "cpu_b": metadata["B"], "same_processor_group": same_group,
                       "same_physical_core": same_core, "same_efficiency_class": same_efficiency,
                       "topology_sha256": comparison.get("topology_sha256")},
        "measurement_settings": settings,
        "run_status_counts": {"successful": sum(len(v) for v in cpu_stats.values()), **statuses},
        "cpu_a_statistics": {**_stats([v for _, v in cpu_stats["A"]]),
                              "run_observations": [{"cycle": cycle, "run_id": by_cycle[cycle]["A"].get("run_id"), "median_ms": value}
                                                   for cycle, value in cpu_stats["A"]]},
        "cpu_b_statistics": {**_stats([v for _, v in cpu_stats["B"]]),
                              "run_observations": [{"cycle": cycle, "run_id": by_cycle[cycle]["B"].get("run_id"), "median_ms": value}
                                                   for cycle, value in cpu_stats["B"]]},
        "cycle_pairs": pairs,
        "aggregate_pair_statistics": {"complete_pair_count": len(pairs),
            "median_b_minus_a_ms": statistics.median(differences) if differences else None,
            "mean_b_minus_a_ms": statistics.mean(differences) if differences else None,
            "minimum_b_minus_a_ms": min(differences) if differences else None,
            "maximum_b_minus_a_ms": max(differences) if differences else None,
            "median_b_over_a_ratio": statistics.median(ratios) if ratios else None},
        "interpretation_limitations": list(LIMITATIONS),
    }


def render_summary(result: dict) -> str:
    c, a, b = result["comparison"], result["cpu_a_statistics"], result["cpu_b_statistics"]
    lines = ["CPU pair analysis", f"Candidate: {c.get('candidate_type')}"]
    for label in ("a", "b"):
        cpu = c.get(f"cpu_{label}")
        lines.append(f"CPU {label.upper()}: " + (f"group {cpu['group_id']} / processor {cpu['processor_number']}" if cpu else "unavailable"))
    lines += [f"Successful runs: A {a['successful_run_count']}, B {b['successful_run_count']}",
              f"Complete pairs: {result['aggregate_pair_statistics']['complete_pair_count']}"]
    for pair in result["cycle_pairs"]:
        lines.append(f"cycle {pair['cycle']}: B-A {pair['b_minus_a_ms']} ms; B/A {pair['b_over_a_ratio']}")
    lines.append(f"Analysis valid: {'yes' if result['analysis_valid'] else 'no'}")
    lines.append("Limitation:")
    lines.extend(result["interpretation_limitations"][:2])
    lines.extend(f"Validation error: {error}" for error in result["validation_errors"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="runs.json or its experiment directory")
    parser.add_argument("--output", type=Path, help="analysis JSON path (default: cpu-pair-analysis.json beside input)")
    args = parser.parse_args(argv)
    source = args.input / "runs.json" if args.input.is_dir() else args.input
    try:
        document = load_runs(source)
    except InputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    result = analyze(document, str(source))
    output = args.output or source.parent / "cpu-pair-analysis.json"
    if output.resolve() == source.resolve():
        print("Output error: analysis output must not overwrite the source runs.json", file=sys.stderr)
        return 2
    try:
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"Output error: {error}", file=sys.stderr)
        return 2
    print(render_summary(result))
    print(f"Analysis JSON: {output}")
    return 0 if result["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
