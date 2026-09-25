"""Validate local C affinity diagnostics and publish reproducible, path-free data."""

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path, PureWindowsPath

if __package__:
    from .diagnose_c_affinity import OPTIONS, build_plan
    from .validate_result_json import validate
else:
    from diagnose_c_affinity import OPTIONS, build_plan
    from validate_result_json import validate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/function_call_numeric_sum/c/main.c"
THRESHOLD_MS = 0.2
SAMPLE_COUNT = 50
CONFIG_KEYS = ("item_count", "warmup_iterations", "measurement_iterations")
PLAN_KEYS = ("experiment_id", "run_number", "number", "cycle", "position",
             "scheduled_order", "condition", "logical_cpu", "run_id", "status")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_file(folder: Path, name: str) -> dict:
    path = folder / name
    if not path.is_file():
        raise ValueError(f"source file is missing: {name}")
    return {"file": name, "sha256": digest(path)}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def _valid_samples(samples) -> bool:
    return (isinstance(samples, list) and len(samples) == SAMPLE_COUNT and
            all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                and value >= 0 for value in samples))


def _aggregate(selected: list[dict]) -> dict:
    successful = [run for run in selected if run["status"] == "success"]
    medians = [statistics.median(run["samples_ms"]) for run in successful]
    return {
        "planned_runs": len(selected),
        "successful_runs": len(successful),
        "failed_runs": sum(run["status"] == "failed" for run in selected),
        "pending_runs": sum(run["status"] == "pending" for run in selected),
        "median_of_medians_ms": statistics.median(medians) if medians else None,
        "mean_median_ms": statistics.mean(medians) if medians else None,
        "stddev_median_ms": statistics.pstdev(medians) if medians else None,
        "min_median_ms": min(medians) if medians else None,
        "max_median_ms": max(medians) if medians else None,
        "measurement_samples": sum(len(run["samples_ms"]) for run in successful),
        "samples_ge_0_2_ms": sum(sum(sample >= THRESHOLD_MS for sample in run["samples_ms"])
                                  for run in successful),
        "runs_with_sample_ge_0_2_ms": sum(any(sample >= THRESHOLD_MS for sample in run["samples_ms"])
                                          for run in successful),
    }


def recalculate(public: dict) -> dict:
    """Recompute every aggregate using only the public run records and samples."""
    runs = public.get("runs")
    planned_conditions = public.get("conditions")
    if not isinstance(runs, list) or not isinstance(planned_conditions, list):
        raise ValueError("public data must contain runs and conditions arrays")
    expected_count = public.get("planned_runs")
    if expected_count != len(runs):
        raise ValueError("planned_runs does not match the published run rows")
    identities = [run.get("run_id") for run in runs]
    if any(not isinstance(value, str) or not value for value in identities) or len(identities) != len(set(identities)):
        raise ValueError("published run IDs are missing or duplicated")
    experiment_ids = {run.get("experiment_id") for run in runs}
    if len(experiment_ids) != 1 or None in experiment_ids:
        raise ValueError("published runs must share one experiment ID")
    experiment_id = next(iter(experiment_ids))
    if not re.fullmatch(r"\d{8}_\d{6}_function_call_numeric_sum", experiment_id):
        raise ValueError("published experiment ID is invalid")
    if public.get("experiment_id") != experiment_id:
        raise ValueError("published experiment ID differs from its run rows")
    condition_keys = {(item.get("condition"), item.get("logical_cpu")) for item in planned_conditions}
    if len(condition_keys) != len(planned_conditions):
        raise ValueError("published conditions are duplicated")
    for index, run in enumerate(runs, 1):
        key = (run.get("condition"), run.get("logical_cpu"))
        if (run.get("run_number") != index or run.get("plan_status") != "pending"
                or run.get("status") not in ("success", "failed", "pending")
                or key not in condition_keys or run.get("position") not in (1, 2, 3)
                or run.get("run_id") != f"{experiment_id[:15]}_c_function_call_numeric_sum_run_{index:03d}"):
            raise ValueError(f"published run {index} does not match the plan")
        samples = run.get("samples_ms")
        if run["status"] == "success":
            if not _valid_samples(samples):
                raise ValueError(f"published successful run {index} must contain exactly 50 finite samples")
            expected_stats = (statistics.median(samples), min(samples), max(samples),
                              sum(sample >= THRESHOLD_MS for sample in samples))
            actual_stats = (run.get("median_ms"), run.get("min_ms"), run.get("max_ms"),
                            run.get("samples_ge_0_2_ms"))
            if actual_stats != expected_stats:
                raise ValueError(f"published run {index} statistics differ from its samples")
        elif samples is not None:
            raise ValueError(f"published non-successful run {index} contains measurement samples")
        elif any(run.get(key) is not None for key in
                 ("median_ms", "min_ms", "max_ms", "samples_ge_0_2_ms")):
            raise ValueError(f"published non-successful run {index} contains sample statistics")
    conditions_summary = []
    for condition in planned_conditions:
        selected = [run for run in runs if (run["condition"], run["logical_cpu"]) ==
                    (condition["condition"], condition["logical_cpu"])]
        conditions_summary.append({"condition": condition["condition"],
                                    "condition_label": condition["condition_label"],
                                    "logical_cpu": condition["logical_cpu"], **_aggregate(selected)})
    positions = []
    for position in (1, 2, 3):
        rows = []
        for condition in planned_conditions:
            selected = [run for run in runs if run["position"] == position and
                        (run["condition"], run["logical_cpu"]) ==
                        (condition["condition"], condition["logical_cpu"])]
            rows.append({"condition": condition["condition"],
                         "condition_label": condition["condition_label"],
                         "logical_cpu": condition["logical_cpu"], **_aggregate(selected)})
        positions.append({"position": position, "conditions": rows})
    return {"conditions": conditions_summary, "positions": positions}


def build_public(folder: Path) -> dict:
    folder = folder.resolve()
    plan_document = load_json(folder / "plan.json")
    record = load_json(folder / "runs.json")
    experiment_id = record.get("experiment_id")
    if (record.get("schema_version") != "1.0" or record.get("benchmark") != "function_call_numeric_sum"
            or record.get("case") != "C/direct" or not isinstance(experiment_id, str)):
        raise ValueError("runs.json is not a supported C/direct affinity diagnostic")
    if not re.fullmatch(r"\d{8}_\d{6}_function_call_numeric_sum", experiment_id):
        raise ValueError("experiment ID is invalid")
    runs = record.get("runs")
    planned = plan_document.get("runs")
    if not isinstance(runs, list) or not isinstance(planned, list) or not runs or len(runs) != len(planned):
        raise ValueError("plan and runs must contain the same non-empty run list")
    if plan_document.get("experiment_id") != experiment_id:
        raise ValueError("experiment ID differs between plan and runs")
    conditions_plan = record.get("conditions")
    if not isinstance(conditions_plan, list) or len(conditions_plan) != 3:
        raise ValueError("the three normal/CPU affinity conditions are required")
    planned_conditions = [(item.get("condition"), item.get("logical_cpu")) for item in conditions_plan]
    if (len(set(planned_conditions)) != 3 or planned_conditions[0] != ("normal", None)
            or any(mode != "affinity" or not isinstance(cpu, int) for mode, cpu in planned_conditions[1:])):
        raise ValueError("condition definitions are invalid")
    stamp = experiment_id.removesuffix("_function_call_numeric_sum")
    expected_plan = build_plan(len(runs) // 3, planned_conditions[1][1], planned_conditions[2][1], stamp)
    if len(runs) != len(expected_plan) or len(runs) % 3:
        raise ValueError("run count does not contain complete three-condition cycles")
    expected_plan_document = {"experiment_id": experiment_id,
                              "runs": [{key: row[key] for key in PLAN_KEYS} for row in expected_plan]}
    if plan_document != expected_plan_document:
        raise ValueError("plan.json differs from the deterministic pending plan")

    config = None
    public_runs = []
    ids = set()
    labels = {planned_conditions[0]: "normal",
              planned_conditions[1]: "CPU A", planned_conditions[2]: "CPU B"}
    binary_hash = record.get("binary_sha256")
    if not isinstance(binary_hash, str) or len(binary_hash) != 64:
        raise ValueError("experiment binary SHA-256 is missing")
    if digest(folder / "c-benchmark.exe") != binary_hash:
        raise ValueError("saved benchmark binary SHA-256 differs from runs.json")
    if record.get("compiler_options") != OPTIONS:
        raise ValueError("compiler options differ from the fixed C benchmark conditions")
    for index, (plan_row, run) in enumerate(zip(planned, runs), 1):
        expected = expected_plan[index - 1]
        if any(plan_row.get(key) != expected[key] for key in PLAN_KEYS):
            raise ValueError(f"plan row {index} differs")
        if any(run.get(key) != expected[key] for key in
               ("experiment_id", "number", "run_number", "cycle", "position", "scheduled_order",
                "condition", "logical_cpu", "run_id")):
            raise ValueError(f"run {index} differs from the precommitted plan")
        if run["run_id"] in ids:
            raise ValueError(f"duplicate run ID: {run['run_id']}")
        ids.add(run["run_id"])
        if run.get("status") not in ("success", "failed", "pending"):
            raise ValueError(f"run {index} has invalid status")
        if not isinstance(run.get("benchmark_config"), dict):
            raise ValueError(f"run {index} benchmark config is missing")
        current_config = {key: run["benchmark_config"].get(key) for key in CONFIG_KEYS}
        if config is None:
            config = current_config
        elif config != current_config:
            raise ValueError("benchmark config changed during the experiment")
        samples = run.get("samples_ms")
        source_result = None
        if run["status"] == "success":
            if current_config != {"item_count": 1000000, "warmup_iterations": 5,
                                  "measurement_iterations": SAMPLE_COUNT}:
                raise ValueError("successful run config differs from the fixed benchmark conditions")
            if not _valid_samples(samples):
                raise ValueError(f"run {index} must contain exactly 50 finite samples")
            if run.get("binary_sha256") != binary_hash:
                raise ValueError(f"run {index} binary SHA-256 differs from the experiment")
            result_name = run.get("result_file")
            if (not isinstance(result_name, str) or Path(result_name).name != result_name
                    or PureWindowsPath(result_name).name != result_name):
                raise ValueError(f"run {index} result filename is invalid")
            result_path = folder / result_name
            result = load_json(result_path)
            errors = validate(result, result_path, allow_affinity_diagnostic_id=True)
            if errors:
                raise ValueError("; ".join(errors))
            expected_affinity = [] if run["logical_cpu"] is None else [f"--diagnostic-affinity={run['logical_cpu']}"]
            argv = result["execution"].get("argv", [])
            affinity_args = [arg for arg in argv if isinstance(arg, str) and arg.startswith("--diagnostic-affinity=")]
            if (result.get("experiment_id") != experiment_id or result.get("run_id") != run["run_id"]
                    or result["config"].get("item_count") != current_config["item_count"]
                    or result["config"].get("warmup_iterations") != current_config["warmup_iterations"]
                    or result["config"].get("measurement_iterations") != current_config["measurement_iterations"]
                    or result["execution"].get("measurement_order") != ["direct", "function_call"]
                    or result["build"].get("compiler") != "gcc"
                    or result["build"].get("compiler_version") != record.get("compiler")
                    or any(option not in result["build"].get("compile_command", "") for option in OPTIONS)
                    or affinity_args != expected_affinity
                    or result["validation"].get("direct_checksum") != 500000500000):
                raise ValueError(f"run {index} source result differs from the planned diagnostic conditions")
            if result["results"]["direct"]["samples_ms"] != samples:
                raise ValueError(f"run {index} samples differ between runs.json and source result")
            if result["optimization_analysis"]["provenance"]["current"]["source_sha256"] != record.get("c_source_sha256"):
                raise ValueError(f"run {index} C source SHA-256 differs from the experiment")
            med, minimum, maximum = statistics.median(samples), min(samples), max(samples)
            slow_count = sum(sample >= THRESHOLD_MS for sample in samples)
            if (run.get("median_ms"), run.get("min_ms"), run.get("max_ms"),
                    run.get("samples_ge_0_2_ms")) != (med, minimum, maximum, slow_count):
                raise ValueError(f"run {index} saved statistics differ from its raw samples")
            source_result = source_file(folder, result_name)
        elif samples is not None:
            raise ValueError(f"non-successful run {index} unexpectedly contains measurement samples")

        condition_key = (run["condition"], run["logical_cpu"])
        public_run = {
            "experiment_id": experiment_id, "run_number": index, "run_id": run["run_id"],
            "cycle": run["cycle"], "position": run["position"],
            "scheduled_order": run["scheduled_order"], "condition": run["condition"],
            "condition_label": labels[condition_key], "logical_cpu": run["logical_cpu"],
            "plan_status": plan_row["status"], "status": run["status"],
            "median_ms": statistics.median(samples) if run["status"] == "success" else None,
            "min_ms": min(samples) if run["status"] == "success" else None,
            "max_ms": max(samples) if run["status"] == "success" else None,
            "samples_ms": samples if run["status"] == "success" else None,
            "samples_ge_0_2_ms": sum(sample >= THRESHOLD_MS for sample in samples) if run["status"] == "success" else None,
        }
        if source_result is not None:
            public_run["source_result"] = source_result
        public_runs.append(public_run)

    source_hash = record.get("c_source_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("C source SHA-256 is missing")
    local_source_hash = hashlib.sha256(SOURCE.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if source_hash != local_source_hash:
        raise ValueError("current C source SHA-256 differs from the diagnostic series")
    if config != {"item_count": 1000000, "warmup_iterations": 5,
                  "measurement_iterations": SAMPLE_COUNT}:
        raise ValueError("benchmark config differs from fixed conditions")

    public_conditions = [{"condition": mode, "condition_label": labels[(mode, cpu)], "logical_cpu": cpu}
                         for mode, cpu in planned_conditions]
    public = {
        "schema_version": "1.0", "benchmark": record["benchmark"], "case": "C/direct",
        "experiment_id": experiment_id, "planned_runs": len(public_runs),
        "conditions": public_conditions,
        "measurement": {
            **config, "measurement_order": ["direct", "function_call"],
            "threshold_ms": THRESHOLD_MS, "compiler": "gcc",
            "compiler_version": record.get("compiler"),
            "compiler_options": record.get("compiler_options"),
        },
        "environment": {
            "os": record["environment"].get("os"), "os_version": record["environment"].get("os_version"),
            "logical_processors": record["environment"].get("logical_processors"),
            "cpu_model": record["environment"].get("cpu_model"),
        },
        "binary_sha256": binary_hash, "c_source_sha256": source_hash,
        "source_files": {
            "plan": source_file(folder, "plan.json"),
            "runs": source_file(folder, "runs.json"),
            "optimization_analysis": source_file(folder, "optimization-analysis.json"),
        },
        "runs": public_runs,
    }
    public["summary"] = recalculate(public)
    return public


def markdown(public: dict) -> str:
    summary = recalculate(public)
    lines = ["# C/direct CPU affinity: 40-cycle, 120-run diagnosis", "",
             "All values are recalculated from this file's run-level medians and 50 raw samples per successful run.",
             "Standard deviation is the population standard deviation of successful run medians. Samples within a run are not treated as independent runs.",
             "The 0.2 ms threshold is descriptive only and does not imply a cause or statistical significance.", "",
             "## Conditions", "",
             "| Condition | Planned | Success | Failed | Pending | Median of run medians (ms) | Mean (ms) | Population SD (ms) | Min (ms) | Max (ms) | Samples | ≥0.2 ms samples | Runs with ≥0.2 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summary["conditions"]:
        lines.append("| {condition_label} | {planned_runs} | {successful_runs} | {failed_runs} | {pending_runs} | {median_of_medians_ms} | {mean_median_ms} | {stddev_median_ms} | {min_median_ms} | {max_median_ms} | {measurement_samples} | {samples_ge_0_2_ms} | {runs_with_sample_ge_0_2_ms} |".format(**row))
    lines += ["", "## Position × condition", "",
              "| Position | Condition | Planned | Success | Failed | Pending | Median (ms) | Mean (ms) | Population SD (ms) | Min (ms) | Max (ms) | Samples | ≥0.2 ms samples | Runs with ≥0.2 ms |",
              "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for position in summary["positions"]:
        for row in position["conditions"]:
            lines.append("| {position} | {condition_label} | {planned_runs} | {successful_runs} | {failed_runs} | {pending_runs} | {median_of_medians_ms} | {mean_median_ms} | {stddev_median_ms} | {min_median_ms} | {max_median_ms} | {measurement_samples} | {samples_ge_0_2_ms} | {runs_with_sample_ge_0_2_ms} |".format(position=position["position"], **row))
    lines += ["", "## Provenance", "",
              f"- Experiment: `{public['experiment_id']}`",
              f"- Binary SHA-256: `{public['binary_sha256']}`",
              f"- C source SHA-256: `{public['c_source_sha256']}`"]
    for name, source in public["source_files"].items():
        lines.append(f"- Raw {name}: `{source['file']}` SHA-256 `{source['sha256']}`")
    lines.append("- Each successful run includes the SHA-256 and filename of its source result JSON.")
    return "\n".join(lines) + "\n"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", help="local results/diagnostics/<series> directory")
    parser.add_argument("--recalculate-public", type=Path,
                        help="recompute and verify the summary from an existing public JSON file only")
    parser.add_argument("--public-output", type=Path, help="destination for generated public JSON")
    parser.add_argument("--table-output", type=Path, help="destination for generated Markdown summary")
    args = parser.parse_args()
    try:
        if args.recalculate_public:
            if args.directory or args.public_output:
                parser.error("--recalculate-public cannot be combined with a raw directory or --public-output")
            public = load_json(args.recalculate_public)
            recalculated = recalculate(public)
            if public.get("summary") != recalculated:
                raise ValueError("stored summary differs from the values recalculated from public runs")
            output = markdown(public)
            if args.table_output:
                write(args.table_output, output)
            else:
                print(json.dumps(recalculated, ensure_ascii=False, indent=2))
            return 0
        if not args.directory or not args.public_output or not args.table_output:
            parser.error("raw directory, --public-output, and --table-output are required")
        public = build_public(args.directory)
        public["summary"] = recalculate(public)
        write(args.public_output, json.dumps(public, ensure_ascii=False, indent=2) + "\n")
        write(args.table_output, markdown(public))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"published_runs={public['planned_runs']} output={args.public_output} summary={args.table_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
