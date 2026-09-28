"""Compare independent CPU pair experiments without joining their timelines."""

import argparse
import json
import statistics
from pathlib import Path

try:
    from .analyze_cpu_pair import analyze, load_runs
    from .cpu_pair_time import load_diagnostics
except ImportError:  # direct CLI invocation
    from analyze_cpu_pair import analyze, load_runs
    from cpu_pair_time import load_diagnostics


def summarize(path):
    source = path / "runs.json" if path.is_dir() else path
    document = load_runs(source)
    result = analyze(document, str(source), diagnostics=load_diagnostics(document, source.parent))
    if not result["analysis_valid"]:
        raise ValueError(f"invalid experiment {source}: {result['validation_errors']}")
    time = result["time_analysis"]
    joint = time["joint_analysis"]
    halves = time["early_late_comparison"]
    busy_by_half = {}
    for half in ("early", "late"):
        cycles = set(halves[f"{half}_cycles"])
        busy_by_half[half] = {}
        for cpu in ("A", "B"):
            values = [row["cpu_busy"]["median_cpu_busy_percent"] for row in time["run_sequence"]
                      if row["cycle"] in cycles and row["comparison_cpu"] == cpu
                      and row["cpu_busy"]["status"] == "available"]
            busy_by_half[half][cpu] = {"sample_count": len(values),
                                       "median_percent": statistics.median(values) if values else None}
    return document, {
        "experiment_id": result["experiment_id"],
        "source_file": str(source),
        "started_at": document["started_at"],
        "compiler": document.get("compiler"),
        "binary_sha256": document.get("binary_sha256"),
        "cycles": result["aggregate_pair_statistics"]["complete_pair_count"],
        "elapsed_seconds": time["experiment_elapsed_seconds"],
        "cpu_a": result["comparison"]["cpu_a"],
        "cpu_b": result["comparison"]["cpu_b"],
        "order_counts": result["round_order_counts"],
        "cpu_a_median_ms": result["cpu_a_statistics"]["median_of_run_medians_ms"],
        "cpu_b_median_ms": result["cpu_b_statistics"]["median_of_run_medians_ms"],
        "elapsed_correlation": joint["elapsed_correlation_by_cpu"],
        "early_late": time["early_late_comparison"],
        "order_effect": result["order_effect"],
        "position_effect": result["position_effect"],
        "cpu_position": joint["by_cpu_and_position"],
        "busy_correlation": joint["busy_correlation_by_cpu"],
        "busy_coverage": {"covered_runs": time["runs_with_diagnostic_coverage"],
                          "successful_runs": time["successful_run_count"],
                          "covered_cycles": joint["busy_covered_cycle_count"]},
        "busy_bands": joint["busy_bands"],
        "busy_by_elapsed_half": busy_by_half,
    }


def compare(paths):
    if len(paths) < 2:
        raise ValueError("at least two experiments are required")
    entries = [summarize(Path(path)) for path in paths]
    documents, summaries = zip(*entries)
    ids = [summary["experiment_id"] for summary in summaries]
    if len(set(ids)) != len(ids):
        raise ValueError("experiment_id must be unique across independent runs")
    first = documents[0]
    for document in documents[1:]:
        if document["comparison"] != first["comparison"]:
            raise ValueError("CPU pair metadata differs between experiments")
        if document["c_source_sha256"] != first["c_source_sha256"]:
            raise ValueError("benchmark source differs between experiments")
        if document.get("compiler") != first.get("compiler"):
            raise ValueError("compiler differs between experiments")
        settings = lambda item: {key: value for key, value in item["measurement_settings"].items()
                                 if key != "runs_per_cpu"}
        if settings(document) != settings(first):
            raise ValueError("measurement settings differ between experiments")
    return {"schema_version": "1.0", "comparison_method": "analyze each experiment separately; never concatenate elapsed observations",
            "experiments": list(summaries)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiments", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare(args.experiments)
        sources = {(path / "runs.json" if path.is_dir() else path).resolve() for path in args.experiments}
        if args.output.resolve() in sources or args.output.exists():
            raise ValueError("output must be a new file distinct from all source files")
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Comparison error: {error}\n")
    for run in result["experiments"]:
        cpu_b = run["early_late"]["by_cpu"]["B"]
        print(f"{run['experiment_id']}: B elapsed r={run['elapsed_correlation']['B']['pearson_r']}; "
              f"B late-early={cpu_b['late_minus_early_ms']} ms")
    print(f"Comparison JSON: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
