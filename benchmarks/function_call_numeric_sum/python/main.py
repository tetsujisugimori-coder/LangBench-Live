import json
import hashlib
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
ANALYSIS_MANIFEST = "artifacts/function-call-analysis/manifest.json"
_DEFAULT_JIT = object()

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
def condition_mismatches(analysis, current):
    mismatches = []
    if analysis.get("source_sha256") != current.get("source_sha256"): mismatches.append("source_sha256")
    if analysis.get("implementation", {}).get("name") != current.get("implementation", {}).get("name"): mismatches.append("implementation.name")
    if analysis.get("implementation", {}).get("version") != current.get("implementation", {}).get("version"): mismatches.append("implementation.version")
    if analysis.get("architecture") != current.get("architecture"): mismatches.append("architecture")
    if analysis.get("options") != current.get("options"): mismatches.append("options")
    return mismatches
def compare_provenance(manifest_entry, current):
    if manifest_entry is None:
        return {"status":"unavailable","artifact_id":None,"analyzed_at":None,"applies_to":["inlining","vectorization","simd"],"analysis":None,"current":current,"matched":False,"mismatches":["manifest_unavailable"]}
    analysis = manifest_entry["condition"]
    mismatches = condition_mismatches(analysis, current)
    return {"status":"matched" if not mismatches else "mismatched","artifact_id":manifest_entry["artifact_id"],"analyzed_at":manifest_entry["analyzed_at"],"applies_to":manifest_entry["applies_to"],"analysis":analysis,"current":current,"matched":not mismatches,"mismatches":mismatches}
def classify_jit(jit_info):
    if jit_info is None:
        return {"applicable": True, "result": "not_checked"}
    try:
        available = jit_info.is_available()
    except Exception:
        return {"applicable": True, "result": "unknown"}
    if not available:
        return {"applicable": False, "result": "not_applicable"}
    try:
        enabled = jit_info.is_enabled()
    except Exception:
        return {"applicable": True, "result": "unknown"}
    return {"applicable": True, "result": "unknown" if enabled else "not_detected"}
def current_analysis_condition(implementation_name=None, implementation_version=None, architecture=None, options=None, source_sha256=None):
    source = Path(__file__).read_bytes()
    return {
        "source_sha256": source_sha256 or hashlib.sha256(source).hexdigest(),
        "implementation": {"name": implementation_name or platform.python_implementation(), "version": implementation_version or platform.python_version()},
        "architecture": architecture or platform.machine().lower(),
        "options": options if options is not None else [f"optimize={sys.flags.optimize}"],
    }
def load_manifest_entry():
    try:
        document = json.loads((project_root() / ANALYSIS_MANIFEST).read_text(encoding="utf-8"))
        return document["languages"][LANGUAGE]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
def optimization_analysis(manifest_entry=None, current=None, jit_info=_DEFAULT_JIT):
    if manifest_entry is None:
        manifest_entry = load_manifest_entry()
    if current is None:
        current = current_analysis_condition()
    if jit_info is _DEFAULT_JIT:
        jit_info = getattr(sys, "_jit", None)
    provenance = compare_provenance(manifest_entry, current)
    saved_result = "not_detected" if provenance["matched"] else ("unknown" if provenance["status"] == "unavailable" else "not_checked")
    jit = classify_jit(jit_info)
    evidence = []
    if jit["result"] in {"detected", "not_detected"}:
        evidence.append({"type":"runtime_api","path":"python:sys._jit.is_available/is_enabled"})
    if provenance["matched"]:
        evidence.extend(manifest_entry["evidence"])
    notes = []
    if provenance["status"] == "mismatched":
        notes.append("Saved CPython bytecode analysis was not applied because these conditions differed: " + ", ".join(provenance["mismatches"]) + ".")
    elif provenance["status"] == "unavailable":
        notes.append("Saved CPython bytecode analysis could not be loaded; its findings are unknown.")
    else:
        notes.append("CPython bytecode retains the add call and scalar loop for this benchmark.")
    notes.append("Native interpreter SIMD instructions were not inspected.")
    return {
        "implementation": current["implementation"],
        "provenance": provenance,
        "jit": jit,
        "inlining": {"result": saved_result},
        "vectorization": {"result": saved_result},
        "simd": {"result": "unknown" if provenance["status"] == "unavailable" else "not_checked", "isa": []},
        "other_optimizations": [],
        "evidence": evidence,
        "notes": notes,
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
