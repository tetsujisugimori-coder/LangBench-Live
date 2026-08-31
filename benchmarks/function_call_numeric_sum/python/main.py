import json
import hashlib
import os
import platform
import re
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
_LOAD_MANIFEST = object()
_INVALID_MANIFEST = object()
OPTIMIZATION_RESULTS = {"detected", "not_detected", "not_checked", "unknown", "not_applicable"}
MANIFEST_LANGUAGES = {"c", "python", "javascript"}
SAVED_FINDING_NAMES_BY_LANGUAGE = {
    "c": {"inlining", "vectorization", "simd"},
    "python": {"inlining", "vectorization", "simd"},
    "javascript": {"jit", "inlining", "vectorization", "simd"},
}
SAVED_FINDING_NAMES = SAVED_FINDING_NAMES_BY_LANGUAGE[LANGUAGE]

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
def valid_condition(condition):
    return (
        isinstance(condition, dict)
        and set(condition) == {"source_sha256", "implementation", "architecture", "options"}
        and isinstance(condition.get("source_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", condition["source_sha256"]) is not None
        and isinstance(condition.get("implementation"), dict)
        and set(condition["implementation"]) == {"name", "version"}
        and all(isinstance(condition["implementation"].get(name), str) and condition["implementation"][name].strip() for name in ("name", "version"))
        and isinstance(condition.get("architecture"), str)
        and bool(condition["architecture"].strip())
        and isinstance(condition.get("options"), list)
        and all(isinstance(option, str) and option.strip() for option in condition["options"])
        and len(condition["options"]) == len(set(condition["options"]))
    )
def valid_findings(findings, expected_names=SAVED_FINDING_NAMES):
    if not isinstance(findings, dict) or set(findings) != expected_names:
        return False
    for name in expected_names - {"simd"}:
        item = findings.get(name)
        if not isinstance(item, dict) or set(item) != {"result"} or item.get("result") not in OPTIMIZATION_RESULTS:
            return False
    simd = findings.get("simd")
    if not isinstance(simd, dict) or set(simd) != {"result", "isa"} or simd.get("result") not in OPTIMIZATION_RESULTS:
        return False
    isa = simd.get("isa")
    return isinstance(isa, list) and all(isinstance(value, str) and value.strip() for value in isa) and len(isa) == len(set(isa)) and bool(isa) == (simd["result"] == "detected")
def valid_manifest_entry(entry, expected_names=SAVED_FINDING_NAMES):
    if not isinstance(entry, dict):
        return False
    if not isinstance(entry.get("artifact_id"), str) or not entry["artifact_id"].strip():
        return False
    if not isinstance(entry.get("analyzed_at"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", entry["analyzed_at"]):
        return False
    applies_to = entry.get("applies_to")
    if not isinstance(applies_to, list) or len(applies_to) != len(expected_names) or set(applies_to) != expected_names:
        return False
    if not valid_condition(entry.get("condition")) or not valid_findings(entry.get("findings"), expected_names):
        return False
    commands = entry.get("generation_commands")
    if not isinstance(commands, list) or not commands or not all(isinstance(part, str) and part.strip() for part in commands):
        return False
    evidence = entry.get("evidence")
    return isinstance(evidence, list) and bool(evidence) and all(
        isinstance(item, dict)
        and set(item) == {"type", "path"}
        and isinstance(item.get("type"), str) and item["type"].strip()
        and isinstance(item.get("path"), str) and item["path"].strip()
        for item in evidence
    )
def valid_manifest_document(document):
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "analysis_id", "generated_at", "languages"}
        or document.get("schema_version") != "1.0"
        or not isinstance(document.get("analysis_id"), str)
        or not document["analysis_id"].strip()
        or not isinstance(document.get("generated_at"), str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", document["generated_at"]) is None
    ):
        return False
    languages = document.get("languages")
    return (
        isinstance(languages, dict)
        and set(languages) == MANIFEST_LANGUAGES
        and all(valid_manifest_entry(languages[name], SAVED_FINDING_NAMES_BY_LANGUAGE[name]) for name in MANIFEST_LANGUAGES)
    )
def compare_provenance(manifest_entry, current):
    if manifest_entry is None:
        return {"status":"unavailable","artifact_id":None,"analyzed_at":None,"applies_to":["inlining","vectorization","simd"],"analysis":None,"artifact_findings":None,"current":current,"matched":False,"mismatches":["manifest_unavailable"]}
    if not valid_manifest_entry(manifest_entry):
        return {"status":"unavailable","artifact_id":None,"analyzed_at":None,"applies_to":["inlining","vectorization","simd"],"analysis":None,"artifact_findings":None,"current":current,"matched":False,"mismatches":["manifest_invalid"]}
    analysis = manifest_entry["condition"]
    mismatches = condition_mismatches(analysis, current)
    return {"status":"matched" if not mismatches else "mismatched","artifact_id":manifest_entry["artifact_id"],"analyzed_at":manifest_entry["analyzed_at"],"applies_to":manifest_entry["applies_to"],"analysis":analysis,"artifact_findings":manifest_entry["findings"],"current":current,"matched":not mismatches,"mismatches":mismatches}
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
def parse_manifest_entry(content):
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return _INVALID_MANIFEST
    if not valid_manifest_document(document):
        return _INVALID_MANIFEST
    return document["languages"][LANGUAGE]
def load_manifest_entry(manifest_path=None):
    try:
        path = Path(manifest_path) if manifest_path is not None else project_root() / ANALYSIS_MANIFEST
        return parse_manifest_entry(path.read_text(encoding="utf-8"))
    except OSError:
        return None
def optimization_analysis(manifest_entry=_LOAD_MANIFEST, current=None, jit_info=_DEFAULT_JIT):
    if manifest_entry is _LOAD_MANIFEST:
        manifest_entry = load_manifest_entry()
    if current is None:
        current = current_analysis_condition()
    if jit_info is _DEFAULT_JIT:
        jit_info = getattr(sys, "_jit", None)
    provenance = compare_provenance(manifest_entry, current)
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
        "inlining": dict(provenance["artifact_findings"]["inlining"]) if provenance["matched"] else {"result": "unknown" if provenance["status"] == "unavailable" else "not_checked"},
        "vectorization": dict(provenance["artifact_findings"]["vectorization"]) if provenance["matched"] else {"result": "unknown" if provenance["status"] == "unavailable" else "not_checked"},
        "simd": {"result": provenance["artifact_findings"]["simd"]["result"], "isa": list(provenance["artifact_findings"]["simd"]["isa"])} if provenance["matched"] else {"result": "unknown" if provenance["status"] == "unavailable" else "not_checked", "isa": []},
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
