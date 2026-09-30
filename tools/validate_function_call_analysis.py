#!/usr/bin/env python3
"""Validate an unpublished function-call analysis package before publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from validate_result_json import validate_analysis_manifest
from extract_function_call_findings import analyze_v8_trace

FILES = {"gcc-optimization.txt", "main.s", "python-bytecode.txt", "manifest.json",
         "v8-optimization-direct_first.txt", "v8-optimization-function_call_first.txt",
         "javascript-order-findings.json"}
FINDING_RESULTS = {"detected", "not_detected", "not_checked", "unknown", "not_applicable"}


def valid_findings(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"jit", "inlining", "vectorization", "simd"}:
        return False
    for name in ("jit", "inlining", "vectorization"):
        item = value[name]
        if (not isinstance(item, dict) or set(item) != {"result"}
                or not isinstance(item["result"], str) or item["result"] not in FINDING_RESULTS):
            return False
    simd = value["simd"]
    return (isinstance(simd, dict) and set(simd) == {"result", "isa"}
            and isinstance(simd["result"], str) and simd["result"] in FINDING_RESULTS and isinstance(simd["isa"], list)
            and all(isinstance(isa, str) and isa for isa in simd["isa"])
            and len(simd["isa"]) == len(set(simd["isa"]))
            and (simd["result"] == "detected") == bool(simd["isa"]))


def validate_package(root: Path, expected_sha: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        saved_findings = json.loads((root / "javascript-order-findings.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"analysis package cannot be read: {exc}"]
    required = {"schema_version", "analysis_id", "code_sha", "generated_at", "operating_system",
                "architecture", "trace_options", "order_coverage", "javascript_orders",
                "trace_is_benchmark", "evidence_sha256"}
    if not isinstance(provenance, dict) or set(provenance) != required:
        return ["provenance fields are invalid"]
    if provenance["schema_version"] != "1.0" or provenance["analysis_id"] != manifest.get("analysis_id"):
        errors.append("provenance identity does not match the analysis manifest")
    code_sha = provenance["code_sha"]
    if not isinstance(code_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        errors.append("code_sha is invalid")
    elif expected_sha is not None and code_sha != expected_sha.lower():
        errors.append("code_sha does not match the trusted main SHA")
    coverage = provenance["order_coverage"]
    expected_basis = {"c": "static_analysis", "python": "static_analysis", "javascript": "trace_observed"}
    if not isinstance(coverage, dict) or set(coverage) != set(expected_basis):
        errors.append("order coverage is invalid")
    else:
        allowed = {"direct_first", "function_call_first"}
        for language, basis in expected_basis.items():
            item = coverage[language]
            if (not isinstance(item, dict) or set(item) != {"basis", "confirmed", "unconfirmed"}
                    or item.get("basis") != basis or not isinstance(item.get("confirmed"), list)
                    or not isinstance(item.get("unconfirmed"), list)
                    or set(item["confirmed"]) | set(item["unconfirmed"]) != allowed
                    or set(item["confirmed"]) & set(item["unconfirmed"])
                    or len(item["confirmed"]) != len(set(item["confirmed"]))
                    or len(item["unconfirmed"]) != len(set(item["unconfirmed"]))):
                errors.append(f"order coverage is invalid for {language}")
    if provenance["trace_is_benchmark"] is not False:
        errors.append("trace execution must not be represented as a benchmark")
    if provenance["trace_options"] != ["--trace-opt", "--trace-deopt", "--trace-turbo-inlining"]:
        errors.append("trace options are not separated from normal benchmark options")
    hashes = provenance["evidence_sha256"]
    if not isinstance(hashes, dict) or set(hashes) != FILES:
        errors.append("evidence hash inventory is invalid")
        hashes = {}
    else:
        for name, expected in hashes.items():
            path = root / name
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                errors.append(f"invalid SHA-256 for {name}")
            elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append(f"evidence was modified or is missing: {name}")
    orders = provenance["javascript_orders"]
    expected_orders = {"direct_first", "function_call_first"}
    if (not isinstance(saved_findings, dict) or set(saved_findings) != expected_orders
            or not all(valid_findings(saved_findings.get(order)) for order in expected_orders)):
        errors.append("saved JavaScript order findings are invalid")
        saved_findings = {}
    if not isinstance(orders, dict) or set(orders) != expected_orders:
        errors.append("JavaScript order findings are invalid")
    else:
        for order in expected_orders:
            item = orders[order]
            evidence = f"v8-optimization-{order}.txt"
            expected_command = ["node", "--trace-opt", "--trace-deopt", "--trace-turbo-inlining",
                                "tools/trace_function_call_javascript.js", order]
            stimulus = {"iterations": 100, "item_count": 10000, "timed": False,
                        "writes_benchmark_result": False}
            trace_path = root / evidence
            try:
                trace = trace_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                trace = ""
            header_valid = (trace.startswith(f"# order={order}\n# exit_code=0\n# stdout\n")
                            and "\n# stderr\n" in trace)
            extracted = analyze_v8_trace(trace) if header_valid else None
            if (not isinstance(item, dict)
                    or set(item) != {"command", "stimulus", "evidence", "evidence_sha256", "findings"}
                    or item.get("command") != expected_command or item.get("stimulus") != stimulus
                    or item.get("evidence") != evidence or item.get("evidence_sha256") != hashes.get(evidence)
                    or item.get("findings") != saved_findings.get(order)
                    or extracted != saved_findings.get(order)):
                errors.append(f"JavaScript order evidence is invalid for {order}")
        if set(saved_findings) == expected_orders:
            consensus: dict[str, dict] = {}
            for name in ("jit", "inlining", "vectorization", "simd"):
                direct = saved_findings["direct_first"].get(name)
                called = saved_findings["function_call_first"].get(name)
                consensus[name] = direct if direct == called else ({"result": "unknown", "isa": []}
                                                                 if name == "simd" else {"result": "unknown"})
            if manifest.get("languages", {}).get("javascript", {}).get("findings") != consensus:
                errors.append("JavaScript manifest findings overgeneralize order-specific evidence")
    errors.extend(validate_analysis_manifest(manifest, root / "manifest.json"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    errors = validate_package(args.directory, args.expected_sha)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("analysis_package=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
