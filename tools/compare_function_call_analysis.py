#!/usr/bin/env python3
"""Compare a validated function-call analysis package with a measurement manifest.

This deliberately keeps exact identity separate from descriptive compatibility.  It
does not infer a performance cause from optimization findings.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from validate_function_call_analysis import validate_package

LANGUAGES = ("c", "python", "javascript")
SOURCE_PATHS = {
    "c": "benchmarks/function_call_numeric_sum/c/main.c",
    "python": "benchmarks/function_call_numeric_sum/python/main.py",
    "javascript": "benchmarks/function_call_numeric_sum/javascript/main.js",
}


def _measurement_hashes(manifest: dict) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in manifest.get("input_sha256", []):
        if not isinstance(item, str) or "=" not in item:
            continue
        path, digest = item.rsplit("=", 1)
        for language, source_path in SOURCE_PATHS.items():
            if path == source_path and re.fullmatch(r"[0-9A-Fa-f]{64}", digest):
                hashes[language] = digest.lower()
    return hashes


def _norm_arch(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return {"amd64": "x64", "x86_64": "x64"}.get(value.lower(), value.lower())


def _measurement_runtime(host: dict, language: str) -> tuple[str, str]:
    raw = str(host[{"c": "gcc", "python": "python", "javascript": "node"}[language]])
    if language == "c":
        match = re.search(r"\b(\d+(?:\.\d+)+)\b", raw)
        return "GCC", match.group(1) if match else raw
    if language == "python":
        return "CPython", raw.removeprefix("Python ")
    return "Node.js", raw


def _version_number(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"\b(\d+(?:\.\d+)+)\b", value)
    return match.group(1) if match else None


def build_comparison(measurement: dict, analysis: dict, provenance: dict) -> dict:
    measured_hashes = _measurement_hashes(measurement)
    if set(measured_hashes) != set(LANGUAGES):
        raise ValueError("measurement manifest does not contain all source hashes")
    host = measurement.get("host")
    if not isinstance(host, dict):
        raise ValueError("measurement host is missing")
    rows = []
    for language in LANGUAGES:
        entry = analysis["languages"][language]
        condition = entry["condition"]
        measured_name, measured_version = _measurement_runtime(host, language)
        implementation = entry["runtime"] if language == "javascript" else condition["implementation"]
        analysis_name = implementation["name"]
        analysis_version = implementation["version"]
        version_match = (_version_number(measured_version) is not None
                         and _version_number(measured_version) == _version_number(analysis_version))
        name_match = analysis_name.casefold() == measured_name.casefold()
        measured_options = host["compile"].get(language, [])
        source_match = measured_hashes[language] == condition["source_sha256"].lower()
        coverage = provenance["order_coverage"][language]
        rows.append({
            "language": language,
            "measurement_source_sha256": measured_hashes[language],
            "analysis_source_sha256": condition["source_sha256"].lower(),
            "source_exact_match": source_match,
            "runtime_or_implementation_match": name_match,
            "version_match": version_match,
            "architecture_match": _norm_arch(host["architecture"]) == _norm_arch(condition["architecture"]),
            "options_match": measured_options == condition["options"],
            "measurement_order": measurement["plan"],
            "analysis_order_coverage": coverage,
            "trace_only": language == "javascript",
            "exact_applicability": all((source_match, name_match, version_match,
                                         _norm_arch(host["architecture"]) == _norm_arch(condition["architecture"]),
                                         measured_options == condition["options"])),
            "impact": "unknown" if not source_match else "not_assessed",
        })
    return {
        "schema_version": "1.0",
        "issue": 68,
        "analysis_id": analysis["analysis_id"],
        "analysis_code_sha": provenance["code_sha"],
        "measurement_series_id": measurement["series_id"],
        "measurement_git_sha": measurement["measurement_git_sha"],
        "trace_is_benchmark": provenance["trace_is_benchmark"],
        "causal_conclusion": "not_established",
        "languages": rows,
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Issue #68: Windows 実機解析と PR #67 の条件照合", "",
        f"- analysis ID: `{result['analysis_id']}`",
        f"- analysis code SHA: `{result['analysis_code_sha']}`",
        f"- measurement series: `{result['measurement_series_id']}`",
        f"- measurement Git SHA: `{result['measurement_git_sha']}`", "",
        "| language | source exact | runtime | version | architecture | options | exact applicability |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["languages"]:
        yes = lambda key: "yes" if row[key] else "no"
        lines.append(f"| {row['language']} | {yes('source_exact_match')} | "
                     f"{yes('runtime_or_implementation_match')} | {yes('version_match')} | "
                     f"{yes('architecture_match')} | {yes('options_match')} | {yes('exact_applicability')} |")
    lines += ["", "JavaScript の trace は性能本測定ではない。条件と観測結果の並置は、最適化が性能差を"
              "生じさせたという因果関係を示さない。source が一致しない場合の影響は unknown とする。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_package", type=Path)
    parser.add_argument("measurement_manifest", type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_package(args.analysis_package, args.expected_sha)
    if errors:
        raise SystemExit("analysis package validation failed:\n" + "\n".join(errors))
    measurement = json.loads(args.measurement_manifest.read_text(encoding="utf-8"))
    analysis = json.loads((args.analysis_package / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((args.analysis_package / "provenance.json").read_text(encoding="utf-8"))
    result = build_comparison(measurement, analysis, provenance)
    args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
