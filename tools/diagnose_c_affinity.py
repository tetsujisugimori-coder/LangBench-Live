"""Windows-only C/direct affinity experiment; keeps normal results and history untouched."""

import argparse
import ctypes
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from validate_result_json import validate
from cpu_topology import analyze_topology, collect_topology


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/function_call_numeric_sum/c/main.c"
OPTIONS = ["-O2", "-std=c11", "-Wall", "-Wextra"]
THRESHOLD_MS = 0.2
COMPARISON_CANDIDATE_TYPES = (
    "same_core_siblings",
    "same_efficiency_class_different_core",
    "different_efficiency_class",
)


class ExperimentInvalidError(RuntimeError):
    """Stop the series when later runs would not be comparable."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allowed_cpu_mask() -> int:
    """Windows process-group mask, also checked by the benchmark itself."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    word = ctypes.c_size_t
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(word), ctypes.POINTER(word)]
    kernel.GetProcessAffinityMask.restype = ctypes.c_int
    process, system = word(), word()
    if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(system)):
        raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask failed")
    return process.value


def check_cpus(cpu_a: int, cpu_b: int, mask: int) -> None:
    if cpu_a == cpu_b:
        raise ValueError("CPU A and CPU B must be distinct")
    for cpu in (cpu_a, cpu_b):
        if cpu < 0 or cpu >= ctypes.sizeof(ctypes.c_size_t) * 8 or not (mask & (1 << cpu)):
            raise ValueError(f"logical CPU {cpu} is outside the process allowed affinity mask 0x{mask:x}")


def conditions(cpu_a: int, cpu_b: int) -> list[tuple[str, int | None]]:
    return [("normal", None), ("affinity", cpu_a), ("affinity", cpu_b)]


def build_plan(repeats: int, cpu_a: int, cpu_b: int, stamp: str) -> list[dict]:
    """Precompute a deterministic three-cycle rotation before any measurement."""
    base = conditions(cpu_a, cpu_b)
    runs = []
    for cycle in range(1, repeats + 1):
        shift = (cycle - 1) % len(base)
        ordered = base[shift:] + base[:shift]
        scheduled_order = ["normal" if cpu is None else f"cpu:{cpu}" for _, cpu in ordered]
        for position, (mode, cpu) in enumerate(ordered, start=1):
            number = len(runs) + 1
            runs.append({
                "experiment_id": f"{stamp}_function_call_numeric_sum",
                "number": number, "run_number": number, "cycle": cycle, "position": position,
                "scheduled_order": scheduled_order, "condition": mode, "logical_cpu": cpu,
                "run_id": f"{stamp}_c_function_call_numeric_sum_run_{number:03d}",
                "started_at": None, "ended_at": None, "status": "pending",
                "result_file": f"run-{number:03d}.json", "binary_sha256": None,
                "benchmark": "C/direct",
                "benchmark_config": {"item_count": 1000000, "warmup_iterations": 5, "measurement_iterations": 50},
                "samples_ms": None, "median_ms": None, "min_ms": None, "max_ms": None,
                "samples_ge_0_2_ms": None, "error": None,
            })
    return runs


def resolve_comparison_candidate(topology: dict, candidate_type: str) -> dict:
    """Return a candidate record or an explicit unavailable reason; never calls OS APIs."""
    if candidate_type not in COMPARISON_CANDIDATE_TYPES:
        raise ValueError(f"unsupported comparison candidate type: {candidate_type}")
    analysis = analyze_topology(topology)
    selection = analysis["comparison_candidates"][candidate_type]
    if selection["candidate"] is None:
        return {"available": False, "unavailable_reason": selection["unavailable_reason"]}
    candidate = selection["candidate"]
    return {
        "available": True,
        "candidate_type": candidate_type,
        "selection_reason": candidate["selection_reason"],
        "cpu_a": {
            "group_id": candidate["first_logical_cpu"]["group_id"],
            "processor_number": candidate["first_logical_cpu"]["processor_number"],
            "physical_core_id": candidate["first_physical_core_id"],
            "efficiency_class": candidate["first_efficiency_class"],
        },
        "cpu_b": {
            "group_id": candidate["second_logical_cpu"]["group_id"],
            "processor_number": candidate["second_logical_cpu"]["processor_number"],
            "physical_core_id": candidate["second_physical_core_id"],
            "efficiency_class": candidate["second_efficiency_class"],
        },
        "same_processor_group": candidate["same_processor_group"],
        "same_physical_core": candidate["same_physical_core"],
        "same_efficiency_class": candidate["same_efficiency_class"],
    }


def candidate_group_unavailable_reason(comparison: dict, active_group_id: int) -> str | None:
    """Current process-affinity implementation can target only its active group."""
    groups = {comparison["cpu_a"]["group_id"], comparison["cpu_b"]["group_id"]}
    if len(groups) != 1:
        return "candidate CPUs belong to different processor groups; cross-group affinity is unsupported"
    group_id = next(iter(groups))
    if group_id != active_group_id:
        return f"candidate processor group {group_id} is not the active process group {active_group_id}"
    return None


def topology_group_unavailable_reason(topology: dict) -> str | None:
    """The C SetProcessAffinityMask runner is intentionally single-group only."""
    group_count = topology.get("processor_group_count")
    if group_count is None:
        group_count = len(topology.get("processor_groups") or [])
    if group_count > 1:
        return "the existing SetProcessAffinityMask runner supports one processor group only"
    return None


def build_comparison_plan(repeats: int, comparison: dict, stamp: str) -> list[dict]:
    """Build a deterministic A/B/A/B pair-only plan with one run per CPU per cycle."""
    if repeats < 1:
        raise ValueError("--runs must be at least 1")
    cpu_a, cpu_b = comparison["cpu_a"], comparison["cpu_b"]
    if (cpu_a["group_id"], cpu_a["processor_number"]) == (cpu_b["group_id"], cpu_b["processor_number"]):
        raise ValueError("comparison candidate must contain two distinct logical CPUs")
    runs = []
    for cycle in range(1, repeats + 1):
        order = [("A", cpu_a), ("B", cpu_b)]
        scheduled_order = [f"cpu_{label.lower()}" for label, _ in order]
        for position, (label, cpu) in enumerate(order, start=1):
            number = len(runs) + 1
            runs.append({
                "experiment_id": f"{stamp}_function_call_numeric_sum",
                "number": number, "run_number": number, "cycle": cycle, "position": position,
                "scheduled_order": scheduled_order, "condition": "affinity", "comparison_cpu": label,
                "logical_cpu": cpu["processor_number"], "processor_group_id": cpu["group_id"],
                # The pair metadata retains group identity; C receives its legacy number-only
                # argument only after single-group validation makes that identity unambiguous.
                "affinity_argument": str(cpu["processor_number"]),
                "run_id": f"{stamp}_c_function_call_numeric_sum_run_{number:03d}",
                "started_at": None, "ended_at": None, "status": "pending",
                "result_file": f"run-{number:03d}.json", "binary_sha256": None,
                "benchmark": "C/direct",
                "benchmark_config": {"item_count": 1000000, "warmup_iterations": 5, "measurement_iterations": 50},
                "samples_ms": None, "median_ms": None, "min_ms": None, "max_ms": None,
                "samples_ge_0_2_ms": None, "error": None,
            })
    return runs


def current_processor_group_id() -> int:
    """Read the calling thread's group for safe use of the legacy process mask API."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class GroupAffinity(ctypes.Structure):
        _fields_ = [("mask", ctypes.c_size_t), ("group", ctypes.c_ushort),
                    ("reserved", ctypes.c_ushort * 3)]

    kernel.GetCurrentThread.restype = ctypes.c_void_p
    kernel.GetThreadGroupAffinity.argtypes = [ctypes.c_void_p, ctypes.POINTER(GroupAffinity)]
    kernel.GetThreadGroupAffinity.restype = ctypes.c_int
    affinity = GroupAffinity()
    if not kernel.GetThreadGroupAffinity(kernel.GetCurrentThread(), ctypes.byref(affinity)):
        raise OSError(ctypes.get_last_error(), "GetThreadGroupAffinity failed")
    return int(affinity.group)


def aggregate(selected: list[dict]) -> dict:
    successful = [run for run in selected if run["status"] == "success"]
    medians = [run["median_ms"] for run in successful]
    return {
        "planned_runs": len(selected),
        "run_count": len(successful), "successful_runs": len(successful),
        "failed_runs": sum(run["status"] == "failed" for run in selected),
        "pending_runs": sum(run["status"] == "pending" for run in selected),
        "median_of_medians_ms": statistics.median(medians) if medians else None,
        "min_median_ms": min(medians) if medians else None,
        "max_median_ms": max(medians) if medians else None,
        "mean_median_ms": statistics.mean(medians) if medians else None,
        # The observed successful runs are the population described by this file.
        "stddev_median_ms": statistics.pstdev(medians) if medians else None,
        "measurement_samples": sum(len(run["samples_ms"]) for run in successful),
        "samples_ge_0_2_ms": sum(run["samples_ge_0_2_ms"] for run in successful),
        "runs_with_sample_ge_0_2_ms": sum(run["samples_ge_0_2_ms"] > 0 for run in successful),
    }


def summarize(runs: list[dict], planned: list[tuple[str, int | None]]) -> list[dict]:
    return [{"condition": mode, "logical_cpu": cpu,
             **aggregate([run for run in runs if run["condition"] == mode and run["logical_cpu"] == cpu])}
            for mode, cpu in planned]


def summarize_positions(runs: list[dict], planned: list[tuple[str, int | None]]) -> list[dict]:
    return [{"position": position, "conditions": [
        {"condition": mode, "logical_cpu": cpu,
         **aggregate([run for run in runs if run["position"] == position and
                      run["condition"] == mode and run["logical_cpu"] == cpu])}
        for mode, cpu in planned]}
        for position in (1, 2, 3)]


def summarize_comparison_positions(runs: list[dict], planned: list[tuple[str, int | None]]) -> list[dict]:
    return [{"position": position, "conditions": [
        {"condition": mode, "logical_cpu": cpu,
         **aggregate([run for run in runs if run["position"] == position and
                      run["condition"] == mode and run["logical_cpu"] == cpu])}
        for mode, cpu in planned]}
        for position in (1, 2)]


def save(path: Path, data: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_binary(binary: Path, expected_hash: str) -> None:
    try:
        actual_hash = sha256(binary)
    except OSError as error:
        raise ExperimentInvalidError(f"cannot verify benchmark binary: {error}") from error
    if actual_hash != expected_hash:
        raise ExperimentInvalidError(f"binary SHA-256 changed: expected {expected_hash}, got {actual_hash}")


def run_checked(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def execute(output: Path, repeats: int, cpu_a: int, cpu_b: int, comparison_metadata: dict | None = None) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("affinity diagnosis requires Windows")
    if repeats < 1:
        raise ValueError("--runs must be at least 1")
    if comparison_metadata:
        group_reason = candidate_group_unavailable_reason(comparison_metadata, current_processor_group_id())
        if group_reason:
            raise ValueError(group_reason)
        if (comparison_metadata["cpu_a"]["processor_number"], comparison_metadata["cpu_b"]["processor_number"]) != (cpu_a, cpu_b):
            raise ValueError("comparison metadata CPU numbers differ from the requested affinity CPUs")
    planned = ([ ("affinity", cpu_a), ("affinity", cpu_b) ]
               if comparison_metadata else conditions(cpu_a, cpu_b))
    check_cpus(cpu_a, cpu_b, allowed_cpu_mask())
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_id = f"{stamp}_function_call_numeric_sum"
    runs = (build_comparison_plan(repeats, comparison_metadata, stamp)
            if comparison_metadata else build_plan(repeats, cpu_a, cpu_b, stamp))
    binary = output / "c-benchmark.exe"
    analysis = output / "optimization-analysis.json"
    source_hash = hashlib.sha256(SOURCE.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    record = {
        "schema_version": "1.0", "benchmark": "function_call_numeric_sum", "case": "C/direct",
        "experiment_id": experiment_id,
        "conditions": [{"condition": mode, "logical_cpu": cpu} for mode, cpu in planned],
        "runs_per_condition": repeats, "binary_sha256": None, "c_source_sha256": source_hash,
        "compiler": None, "compiler_options": OPTIONS, "compile_ms": None,
        "environment": {"os": platform.platform(), "logical_processors": os.cpu_count(), "cpu_model": platform.processor() or None},
        "started_at": now(), "ended_at": None, "runs": runs, "summary": [],
    }
    if comparison_metadata:
        record["comparison"] = comparison_metadata
        record["measurement_settings"] = {
            "benchmark_identifier": "function_call_numeric_sum",
            "language": "C",
            "case": "C/direct",
            "item_count": 1000000,
            "warmup_iterations": 5,
            "measurement_iterations": 50,
            "measurement_order": ["direct", "function_call"],
            "runs_per_cpu": repeats,
            "pair_run_order": "CPU A then CPU B, repeated",
            "compiler_options": list(OPTIONS),
            "affinity_is_the_only_configured_run_difference": True,
        }
    plan_fields = ("experiment_id", "run_number", "number", "cycle", "position", "scheduled_order",
                   "condition", "logical_cpu", "run_id", "status")
    if comparison_metadata:
        plan_fields += ("comparison_cpu", "processor_group_id", "affinity_argument", "benchmark_config")
    plan_document = {"experiment_id": experiment_id,
                     "runs": [{name: run[name] for name in plan_fields} for run in runs]}
    if comparison_metadata:
        plan_document["comparison"] = comparison_metadata
        plan_document["measurement_settings"] = record["measurement_settings"]
    save(output / "plan.json", plan_document)
    save(output / "runs.json", record)
    runner = ROOT / "benchmarks/function_call_numeric_sum/c/run_c.ps1"
    analysis.write_text(run_checked(["pwsh", "-NoProfile", "-File", str(runner), "-ResolveAnalysisOnly"]).stdout.strip(), encoding="utf-8")
    compiler_version = run_checked(["gcc", "--version"]).stdout.splitlines()[0].removeprefix("gcc.exe ")
    command = ["gcc", str(SOURCE), *OPTIONS, "-o", str(binary)]
    start_compile = datetime.now().timestamp()
    run_checked(command)
    compile_ms = round((datetime.now().timestamp() - start_compile) * 1000, 3)
    binary_hash = sha256(binary)
    record.update(binary_sha256=binary_hash, compiler=compiler_version, compile_ms=compile_ms)
    save(output / "runs.json", record)
    # Execute the immutable precommitted order, leaving future runs pending if interrupted.
    for run in runs:
        number, mode, cpu = run["number"], run["condition"], run["logical_cpu"]
        result_path = output / run["result_file"]
        arguments = [str(binary), str(compile_ms), compiler_version, subprocess.list2cmdline(command), str(SOURCE), str(analysis),
                     f"--experiment-id={experiment_id}", f"--run-id={run['run_id']}",
                     "--measurement-order=direct_first", f"--result-path={result_path}"]
        if cpu is not None:
            arguments.append(f"--diagnostic-affinity={run.get('affinity_argument', cpu)}")
        run["started_at"] = now()
        save(output / "runs.json", record)
        fatal_error = None
        try:
            verify_binary(binary, binary_hash)
            run["binary_sha256"] = binary_hash
            process = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True)
            (output / f"run-{number:03d}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            verify_binary(binary, binary_hash)
            if process.returncode:
                if cpu is not None and any(marker in process.stderr for marker in
                        ("GetProcessAffinityMask", "SetProcessAffinityMask", "affinity verification failed",
                         "outside the process allowed affinity mask", "invalid logical CPU number")):
                    raise ExperimentInvalidError(f"affinity verification failed: {process.stderr.strip()}")
                raise RuntimeError(f"benchmark exited {process.returncode}: {process.stderr.strip()}")
            document = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(document, dict) and isinstance(document.get("config"), dict) and any(
                    document["config"].get(key) != value for key, value in run["benchmark_config"].items()):
                raise ExperimentInvalidError("benchmark config differs from fixed conditions")
            if isinstance(document, dict) and isinstance(document.get("execution"), dict):
                argv = document["execution"].get("argv")
                if isinstance(argv, list):
                    affinity_args = [arg for arg in argv if isinstance(arg, str) and arg.startswith("--diagnostic-affinity=")]
                    expected_affinity = run.get("affinity_argument", cpu)
                    if affinity_args != ([] if cpu is None else [f"--diagnostic-affinity={expected_affinity}"]):
                        raise ExperimentInvalidError("affinity argument differs from the plan")
                if document["execution"].get("measurement_order") != ["direct", "function_call"]:
                    raise ExperimentInvalidError("measurement order differs from fixed conditions")
            errors = validate(document, result_path, allow_affinity_diagnostic_id=True)
            if errors:
                raise ValueError("; ".join(errors))
            if document["run_id"] != run["run_id"] or document["experiment_id"] != experiment_id:
                raise ValueError("result IDs differ from the precommitted plan")
            samples = document["results"]["direct"]["samples_ms"]
            if len(samples) != 50 or document["validation"]["direct_checksum"] != 500000500000:
                raise ValueError("direct samples or checksum differ from fixed conditions")
            if number == 1:
                environment = document["environment"]
                record["environment"] = {
                    "os": environment["os"], "os_version": environment["os_version"],
                    "logical_processors": environment["logical_processors"], "cpu_model": environment["cpu"],
                }
            run.update(samples_ms=samples, median_ms=statistics.median(samples), min_ms=min(samples), max_ms=max(samples),
                       samples_ge_0_2_ms=sum(sample >= THRESHOLD_MS for sample in samples), status="success")
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            run.update(status="failed", error=str(error))
            if isinstance(error, ExperimentInvalidError):
                fatal_error = error
        finally:
            run["ended_at"] = now()
            record["summary"] = summarize(record["runs"], planned)
            save(output / "runs.json", record)
        print(f"run={number} condition={mode} cpu={cpu} status={run['status']}", flush=True)
        if fatal_error is not None:
            raise fatal_error
    record["ended_at"] = now()
    save(output / "runs.json", record)
    positions = (summarize_comparison_positions(runs, planned) if comparison_metadata
                 else summarize_positions(runs, planned))
    save(output / "summary.json", {"experiment_id": experiment_id, "binary_sha256": binary_hash,
                                   "planned_runs": len(runs), "conditions": record["summary"],
                                   "positions": positions})
    for row in record["summary"]:
        print(f"{row['condition']} cpu={row['logical_cpu']} runs={row['run_count']} median_of_medians_ms={row['median_of_medians_ms']} "
              f"median_range_ms={row['min_median_ms']}..{row['max_median_ms']} slow_samples={row['samples_ge_0_2_ms']} "
              f"slow_runs={row['runs_with_sample_ge_0_2_ms']}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, help="runs per CPU (default: 40 legacy, 2 candidate comparison)")
    parser.add_argument("--cpu-a", type=int, default=0)
    parser.add_argument("--cpu-b", type=int, default=1)
    parser.add_argument("--candidate-type", choices=COMPARISON_CANDIDATE_TYPES,
                        help="compare the two logical CPUs selected by this topology candidate")
    parser.add_argument("--output", type=Path, help="new diagnostic output directory (must not already exist)")
    args = parser.parse_args()
    try:
        if args.candidate_type:
            if sys.platform != "win32":
                print("Comparison unavailable: CPU affinity comparison requires Windows.", file=sys.stderr)
                return 2
            topology = collect_topology()
            if topology.get("status") != "available":
                print(f"Comparison unavailable: CPU topology status is {topology.get('status')!r}: "
                      f"{topology.get('error', 'no topology details')}", file=sys.stderr)
                return 2
            group_reason = topology_group_unavailable_reason(topology)
            if group_reason:
                print(f"Comparison unavailable for {args.candidate_type}: {group_reason}", file=sys.stderr)
                return 2
            comparison = resolve_comparison_candidate(topology, args.candidate_type)
            if not comparison["available"]:
                print(f"Comparison unavailable for {args.candidate_type}: {comparison['unavailable_reason']}",
                      file=sys.stderr)
                return 2
            active_group = current_processor_group_id()
            group_reason = candidate_group_unavailable_reason(comparison, active_group)
            if group_reason:
                print(f"Comparison unavailable for {args.candidate_type}: {group_reason}", file=sys.stderr)
                return 2
            try:
                check_cpus(comparison["cpu_a"]["processor_number"], comparison["cpu_b"]["processor_number"],
                           allowed_cpu_mask())
            except ValueError as error:
                print(f"Comparison unavailable for {args.candidate_type}: {error}", file=sys.stderr)
                return 2
            topology_bytes = json.dumps(topology, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")
            comparison["active_processor_group_id"] = active_group
            comparison["topology_sha256"] = hashlib.sha256(topology_bytes).hexdigest()
            cpu_a = comparison["cpu_a"]["processor_number"]
            cpu_b = comparison["cpu_b"]["processor_number"]
            runs = args.runs if args.runs is not None else 2
            output = args.output or ROOT / "results/diagnostics" / (
                f"cpu-pair-{args.candidate_type}-{datetime.now():%Y%m%d_%H%M%S}")
            print(f"Candidate {args.candidate_type}: group {active_group} CPU {cpu_a} vs CPU {cpu_b}")
            print(f"Order: group {active_group} CPU A, CPU B, alternating for {runs} run(s) per CPU")
            record = execute(output, runs, cpu_a, cpu_b, comparison)
        else:
            runs = args.runs if args.runs is not None else 40
            output = args.output or ROOT / "results/diagnostics" / f"c-affinity-{datetime.now():%Y%m%d_%H%M%S}"
            record = execute(output, runs, args.cpu_a, args.cpu_b)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0 if all(run["status"] == "success" for run in record["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
