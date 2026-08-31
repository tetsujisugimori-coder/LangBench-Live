#!/usr/bin/env python3
"""Derive function-call benchmark findings from generated analysis artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _result(value: str) -> dict[str, str]:
    return {"result": value}


def _simd(value: str, isa: list[str] | None = None) -> dict[str, Any]:
    return {"result": value, "isa": isa or []}


def _assembly_function(assembly: str, name: str) -> str:
    label = re.search(rf'(?m)^\s*"?{re.escape(name)}"?:\s*$', assembly)
    if label is None:
        return ""
    tail = assembly[label.end():]
    endings = [
        re.search(r"(?m)^\s*\.seh_endproc\s*$", tail),
        re.search(r"(?m)^\s*\.cfi_endproc\s*$", tail),
        re.search(rf'(?m)^\s*\.size\s+"?{re.escape(name)}"?\s*,', tail),
    ]
    offsets = [match.start() for match in endings if match is not None]
    return tail[:min(offsets)] if offsets else tail


def analyze_c_artifacts(report: str, assembly: str, architecture: str) -> dict[str, Any]:
    """Return only conclusions supported by the GCC report and target functions."""
    direct_body = _assembly_function(assembly, "direct_sum")
    called_body = _assembly_function(assembly, "function_call_sum")
    call_retained = bool(re.search(r'(?im)\bcall\w*\s+"?_?add"?\b', called_body))
    report_vectorized = bool(re.search(r"(?im)optimized:\s+loop vectorized\b", report))
    packed_integer_vector = bool(
        re.search(r"(?im)\b(?:padd[bdqwd]|vpadd\w*|punpck\w*|movdqu)\b", direct_body)
    )
    vectorized = report_vectorized and packed_integer_vector

    normalized_arch = architecture.lower()
    is_x86 = normalized_arch in {"x64", "amd64", "x86_64", "x86", "i386", "i686"}
    sse2_confirmed = is_x86 and bool(
        re.search(r"(?im)\bpaddq\b", direct_body)
        and re.search(r"(?im)\bxmm\d+\b", direct_body)
    )
    return {
        "inlining": _result("not_detected" if call_retained else "not_checked"),
        "vectorization": _result("detected" if vectorized else "not_checked"),
        "simd": _simd("detected", ["SSE2"]) if sse2_confirmed else _simd("not_checked"),
    }


def analyze_python_bytecode(bytecode: str) -> dict[str, Any]:
    """Derive CPython bytecode findings for the function_call code object."""
    match = re.search(
        r"(?ms)^Disassembly of <code object function_call\b.*?>:\s*(.*?)(?=^Disassembly of <code object |\Z)",
        bytecode,
    )
    body = match.group(1) if match else ""
    add_call = bool(re.search(r"(?m)LOAD_GLOBAL\s+\d+\s+\(add(?: \+ NULL)?\)", body) and re.search(r"(?m)\bCALL\s+\d+", body))
    scalar_loop = "FOR_ITER" in body
    return {
        "inlining": _result("not_detected" if add_call else "not_checked"),
        "vectorization": _result("not_detected" if scalar_loop else "not_checked"),
        "simd": _simd("not_checked"),
    }


def analyze_v8_trace(trace: str) -> dict[str, Any]:
    """Derive V8 findings only from records naming the benchmark functions."""
    if not trace.strip():
        jit_result = inlining_result = "unknown"
    else:
        jit_result = "detected" if re.search(
            r"(?im)^\[completed optimizing .*<JSFunction called\b", trace
        ) else "not_checked"
        inlining_result = "detected" if re.search(
            r"(?im)^Inlining .*<SharedFunctionInfo add>} into .*<SharedFunctionInfo called>}\s*$",
            trace,
        ) else "not_checked"
    return {
        "jit": _result(jit_result),
        "inlining": _result(inlining_result),
        "vectorization": _result("not_checked"),
        "simd": _simd("not_checked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, choices=("c", "python", "javascript"))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--assembly", type=Path)
    parser.add_argument("--architecture")
    args = parser.parse_args()

    if args.language == "c":
        if args.report is None or args.assembly is None or not args.architecture:
            parser.error("C extraction requires --report, --assembly, and --architecture")
        findings = analyze_c_artifacts(
            args.report.read_text(encoding="utf-8", errors="replace"),
            args.assembly.read_text(encoding="utf-8", errors="replace"),
            args.architecture,
        )
    else:
        if args.artifact is None:
            parser.error("Python and JavaScript extraction require --artifact")
        content = args.artifact.read_text(encoding="utf-8", errors="replace")
        findings = analyze_python_bytecode(content) if args.language == "python" else analyze_v8_trace(content)
    print(json.dumps(findings, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
