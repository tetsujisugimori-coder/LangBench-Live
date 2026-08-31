import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = "LangBench Live"
SCHEMA_VERSION = "1.0"
LANGUAGE = "python"
BENCHMARK = "function_call_numeric_sum"
ITEM_COUNT = 1_000_000
WARMUP_ITERATIONS = 5
MEASUREMENT_ITERATIONS = 50
EXPECTED_CHECKSUM = ITEM_COUNT * (ITEM_COUNT + 1) // 2
RESULT_FILE = "function_call_numeric_sum_python_result.json"

def project_root(): return Path(__file__).resolve().parents[3]
def now_ms(): return time.perf_counter_ns() / 1_000_000
def rounded(value): return round(value, 3)
def arg(name): return next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith(name + "=")), None)
def stamp(): return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
def experiment_id(): return arg("--experiment-id") or os.getenv("LANGBENCH_EXPERIMENT_ID") or f"{stamp()}_{BENCHMARK}"
def run_id(): return arg("--run-id") or os.getenv("LANGBENCH_RUN_ID") or f"{stamp()}_{LANGUAGE}_{BENCHMARK}"

def direct(values):
    total = 0
    for value in values: total += value
    return total
def add(current, value): return current + value
def function_call(values):
    total = 0
    for value in values: total = add(total, value)
    return total
def stats(samples):
    ordered = sorted(samples); mid = len(ordered) // 2
    return {"samples_ms": samples, "min_ms": rounded(min(samples)), "max_ms": rounded(max(samples)), "mean_ms": rounded(sum(samples) / len(samples)), "median_ms": rounded((ordered[mid - 1] + ordered[mid]) / 2)}
def measure(case, values):
    warmup_start = now_ms()
    for _ in range(WARMUP_ITERATIONS):
        if case(values) != EXPECTED_CHECKSUM: raise RuntimeError("warmup checksum mismatch")
    warmup_ms = rounded(now_ms() - warmup_start); samples = []; checksum = None
    for _ in range(MEASUREMENT_ITERATIONS):
        start = now_ms(); checksum = case(values); samples.append(rounded(now_ms() - start))
        if checksum != EXPECTED_CHECKSUM: raise RuntimeError("checksum mismatch")
    return warmup_ms, rounded(sum(samples)), checksum, stats(samples)
def metadata(status, eid, rid):
    return {"type":"langbench_result", "schema_version":SCHEMA_VERSION, "project":PROJECT, "benchmark":BENCHMARK, "experiment_id":eid, "run_id":rid, "language":LANGUAGE, "created_at":datetime.now().astimezone().isoformat(timespec="milliseconds"), "status":status, "engine":{"runtime":"python", "runtime_version":platform.python_version(), "compiler":None, "compiler_version":None, "python_implementation":platform.python_implementation()}, "execution":{"runner":"vscode_terminal_powershell", "runner_label":"VSCode Terminal / PowerShell", "cwd":str(Path.cwd()), "argv":[sys.executable, *sys.argv]}, "environment":{"os":platform.system() or None, "os_version":platform.version() or None, "architecture":platform.machine() or None, "cpu":platform.processor() or None, "logical_processors":os.cpu_count(), "memory_bytes":None}, "build":None}
def jit_analysis():
    jit = getattr(sys, "_jit", None)
    if jit is None:
        if platform.python_implementation() == "CPython":
            return {"applicable": False, "result": "not_applicable"}
        return {"applicable": True, "result": "not_checked"}
    try:
        enabled = jit.is_enabled()
    except Exception:
        return {"applicable": True, "result": "unknown"}
    return {"applicable": True, "result": "unknown" if enabled else "not_detected"}
def optimization_analysis():
    return {
        "implementation": {"name": platform.python_implementation(), "version": platform.python_version()},
        "jit": jit_analysis(),
        "inlining": {"result": "not_detected"},
        "vectorization": {"result": "not_detected"},
        "simd": {"result": "not_checked", "isa": []},
        "other_optimizations": [],
        "evidence": [{"type": "disassembly", "path": "artifacts/function-call-analysis/python-bytecode.txt"}],
        "notes": [
            "CPython bytecode retains the add call and scalar loop for this benchmark.",
            "Native interpreter SIMD instructions were not inspected.",
        ],
    }
def run(eid, rid):
    setup_start = now_ms(); values = list(range(1, ITEM_COUNT + 1)); setup_ms = rounded(now_ms() - setup_start)
    direct_warmup, direct_measurement, direct_sum, direct_results = measure(direct, values)
    call_warmup, call_measurement, call_sum, call_results = measure(function_call, values)
    warmup_ms = rounded(direct_warmup + call_warmup); measurement_ms = rounded(direct_measurement + call_measurement)
    return {**metadata("success", eid, rid), "optimization_analysis":optimization_analysis(), "config":{"item_count":ITEM_COUNT,"warmup_iterations":WARMUP_ITERATIONS,"measurement_iterations":MEASUREMENT_ITERATIONS,"numeric_type":"integer","value_field":"value","cases":["direct","function_call"]}, "timing":{"process_startup_ms":None,"setup_ms":setup_ms,"warmup_ms":warmup_ms,"measurement_ms":measurement_ms,"benchmark_total_ms":rounded(setup_ms + warmup_ms + measurement_ms)}, "results":{"direct":direct_results,"function_call":call_results}, "validation":{"direct_checksum":direct_sum,"function_call_checksum":call_sum,"expected_checksum":EXPECTED_CHECKSUM,"tolerance":0,"passed":direct_sum == call_sum == EXPECTED_CHECKSUM}, "error":None}
def main():
    eid, rid = experiment_id(), run_id()
    try:
        result = run(eid, rid); (project_root() / "results").mkdir(exist_ok=True)
        (project_root() / "results" / RESULT_FILE).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("status=success"); return 0
    except Exception as error:
        print("status=error", file=sys.stderr); print(f"message={error}", file=sys.stderr); return 1
if __name__ == "__main__": raise SystemExit(main())
