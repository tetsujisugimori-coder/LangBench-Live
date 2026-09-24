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


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/function_call_numeric_sum/c/main.c"
OPTIONS = ["-O2", "-std=c11", "-Wall", "-Wextra"]
THRESHOLD_MS = 0.2


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
                "number": number, "cycle": cycle, "position": position,
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


def summarize(runs: list[dict], planned: list[tuple[str, int | None]]) -> list[dict]:
    summary = []
    for mode, cpu in planned:
        selected = [run for run in runs if run["status"] == "success" and run["condition"] == mode and run["logical_cpu"] == cpu]
        medians = [run["median_ms"] for run in selected]
        summary.append({
            "condition": mode, "logical_cpu": cpu, "run_count": len(selected),
            "median_of_medians_ms": statistics.median(medians) if medians else None,
            "min_median_ms": min(medians) if medians else None,
            "max_median_ms": max(medians) if medians else None,
            "samples_ge_0_2_ms": sum(run["samples_ge_0_2_ms"] for run in selected),
            "runs_with_sample_ge_0_2_ms": sum(run["samples_ge_0_2_ms"] > 0 for run in selected),
        })
    return summary


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def execute(output: Path, repeats: int, cpu_a: int, cpu_b: int) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("affinity diagnosis requires Windows")
    if repeats < 1:
        raise ValueError("--runs must be at least 1")
    planned = conditions(cpu_a, cpu_b)
    check_cpus(cpu_a, cpu_b, allowed_cpu_mask())
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_id = f"{stamp}_function_call_numeric_sum"
    runs = build_plan(repeats, cpu_a, cpu_b, stamp)
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
    plan_fields = ("number", "cycle", "position", "scheduled_order", "condition", "logical_cpu", "run_id", "status")
    save(output / "plan.json", {"experiment_id": experiment_id,
                               "runs": [{name: run[name] for name in plan_fields} for run in runs]})
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
    for run in runs:
        run["binary_sha256"] = binary_hash
    save(output / "runs.json", record)
    # Execute the immutable precommitted order, leaving future runs pending if interrupted.
    for run in runs:
        number, mode, cpu = run["number"], run["condition"], run["logical_cpu"]
        result_path = output / run["result_file"]
        arguments = [str(binary), str(compile_ms), compiler_version, subprocess.list2cmdline(command), str(SOURCE), str(analysis),
                     f"--experiment-id={experiment_id}", f"--run-id={run['run_id']}",
                     "--measurement-order=direct_first", f"--result-path={result_path}"]
        if cpu is not None:
            arguments.append(f"--diagnostic-affinity={cpu}")
        run["started_at"] = now()
        save(output / "runs.json", record)
        try:
            process = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True)
            (output / f"run-{number:03d}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            if process.returncode:
                raise RuntimeError(f"benchmark exited {process.returncode}: {process.stderr.strip()}")
            document = json.loads(result_path.read_text(encoding="utf-8"))
            errors = validate(document, result_path, allow_affinity_diagnostic_id=True)
            if errors:
                raise ValueError("; ".join(errors))
            if document["run_id"] != run["run_id"] or document["experiment_id"] != experiment_id:
                raise ValueError("result IDs differ from the precommitted plan")
            if document["config"]["item_count"] != 1000000 or document["config"]["warmup_iterations"] != 5 or document["config"]["measurement_iterations"] != 50:
                raise ValueError("benchmark config differs from fixed conditions")
            samples = document["results"]["direct"]["samples_ms"]
            if len(samples) != 50 or document["validation"]["direct_checksum"] != 500000500000:
                raise ValueError("direct samples or checksum differ from fixed conditions")
            if number == 1:
                environment = document["environment"]
                record["environment"] = {
                    "os": environment["os"], "os_version": environment["os_version"],
                    "logical_processors": environment["logical_processors"], "cpu_model": environment["cpu"],
                }
            if sha256(binary) != binary_hash:
                raise ValueError("binary changed during diagnosis")
            run.update(samples_ms=samples, median_ms=statistics.median(samples), min_ms=min(samples), max_ms=max(samples),
                       samples_ge_0_2_ms=sum(sample >= THRESHOLD_MS for sample in samples), status="success")
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            run.update(status="failed", error=str(error))
        finally:
            run["ended_at"] = now()
            record["summary"] = summarize(record["runs"], planned)
            save(output / "runs.json", record)
        print(f"run={number} condition={mode} cpu={cpu} status={run['status']}", flush=True)
    record["ended_at"] = now()
    save(output / "runs.json", record)
    save(output / "summary.json", {"binary_sha256": binary_hash, "conditions": record["summary"]})
    for row in record["summary"]:
        print(f"{row['condition']} cpu={row['logical_cpu']} runs={row['run_count']} median_of_medians_ms={row['median_of_medians_ms']} "
              f"median_range_ms={row['min_median_ms']}..{row['max_median_ms']} slow_samples={row['samples_ge_0_2_ms']} "
              f"slow_runs={row['runs_with_sample_ge_0_2_ms']}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=40, help="runs per condition (default: 40)")
    parser.add_argument("--cpu-a", type=int, default=0)
    parser.add_argument("--cpu-b", type=int, default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "results/diagnostics" / f"c-affinity-{datetime.now():%Y%m%d_%H%M%S}")
    args = parser.parse_args()
    try:
        record = execute(args.output, args.runs, args.cpu_a, args.cpu_b)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0 if all(run["status"] == "success" for run in record["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
