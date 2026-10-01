#!/usr/bin/env python3
"""Compare the validated Issue #68 Windows analysis with PR #67 public measurement."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

from validate_function_call_analysis import validate_package

LANGUAGES = ("c", "python", "javascript")
ORDERS = {"direct_first", "function_call_first"}
MEASUREMENT_SHA256 = "60a5b14eeb8f287910b248e832a177264593682eda3952f06219e4a13a49c4a4"
MEASUREMENT_GIT_SHA = "fde3f78b385034248bac9dfe7a97c8da37ffb3ae"
MEASUREMENT_SERIES = "issue66-balanced-final-01"
ANALYSIS_ID = "issue68-pra-69-36797708544"
ANALYSIS_CODE_SHA = "98dbb01d36c204f352d5b4690de72b570fdb075e"
SOURCE_PATHS = {
    "c": "benchmarks/function_call_numeric_sum/c/main.c",
    "python": "benchmarks/function_call_numeric_sum/python/main.py",
    "javascript": "benchmarks/function_call_numeric_sum/javascript/main.js",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def validate_measurement(measurement: dict, digest: str) -> dict:
    expected = {
        "sha256": MEASUREMENT_SHA256,
        "measurement_git_sha": MEASUREMENT_GIT_SHA,
        "series_id": MEASUREMENT_SERIES,
        "issue": 66,
        "benchmark": "function_call_numeric_sum",
        "status": "completed",
    }
    actual = {"sha256": digest}
    actual.update({key: measurement.get(key) for key in expected if key != "sha256"})
    if actual != expected:
        raise ValueError(f"PR #67 measurement identity mismatch: {actual!r}")
    return {"expected": expected, "actual": actual}


def _norm_arch(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return {"amd64": "x64", "x86_64": "x64"}.get(value.lower(), value.lower())


def _version(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    match = re.search(r"\b(\d+(?:\.\d+)+)\b", value)
    return match.group(1) if match else None


def _match_identity(expected: dict, actual: dict) -> bool:
    if (not isinstance(expected.get("name"), str) or not isinstance(actual.get("name"), str)
            or expected["name"].casefold() != actual["name"].casefold()):
        return False
    name = expected["name"].casefold()
    expected_version, actual_version = expected.get("version"), actual.get("version")
    if not isinstance(expected_version, str) or not isinstance(actual_version, str):
        return False
    if name == "v8":
        return expected_version == actual_version
    if name == "node.js":
        return expected_version.removeprefix("v") == actual_version.removeprefix("v")
    return (_version(expected_version) is not None
            and _version(expected_version) == _version(actual_version))


def _measurement_environment(host: dict, language: str) -> tuple[dict, dict | None]:
    if language == "c":
        value = host.get("gcc")
        identity = {"name": "GCC", "version": value}
        return identity, identity
    if language == "python":
        value = host.get("python")
        identity = {"name": "CPython", "version": value}
        return identity, identity
    runtime = {"name": "Node.js", "version": host.get("node")}
    # PR #67's public manifest records Node.js but no independently measured V8 version.
    v8 = host.get("v8")
    implementation = {"name": "V8", "version": v8} if isinstance(v8, str) else None
    return runtime, implementation


def _coverage(provenance: dict, language: str) -> tuple[object, bool]:
    coverage = provenance.get("order_coverage", {}).get(language)
    expected_basis = "trace_observed" if language == "javascript" else "static_analysis"
    valid = (isinstance(coverage, dict) and coverage.get("basis") == expected_basis
             and isinstance(coverage.get("confirmed"), list)
             and isinstance(coverage.get("unconfirmed"), list)
             and len(coverage["confirmed"]) == 2
             and set(coverage["confirmed"]) == ORDERS
             and coverage["unconfirmed"] == [])
    return coverage, bool(valid)


def build_comparison(measurement: dict, analysis: dict, provenance: dict,
                     measurement_sha256: str) -> dict:
    identity = validate_measurement(measurement, measurement_sha256)
    if analysis.get("analysis_id") != ANALYSIS_ID or provenance.get("code_sha") != ANALYSIS_CODE_SHA:
        raise ValueError("analysis identity mismatch")
    measured_hashes = _measurement_hashes(measurement)
    if set(measured_hashes) != set(LANGUAGES):
        raise ValueError("measurement manifest does not contain all source hashes")
    host = measurement.get("host")
    if not isinstance(host, dict) or not isinstance(host.get("compile"), dict):
        raise ValueError("measurement host or compile options are missing")
    rows = []
    for language in LANGUAGES:
        entry = analysis["languages"][language]
        condition = entry["condition"]
        runtime, implementation = _measurement_environment(host, language)
        analysis_runtime = entry.get("runtime", condition["implementation"])
        analysis_implementation = condition["implementation"]
        runtime_match = _match_identity(runtime, analysis_runtime)
        implementation_match = (implementation is not None
                                and _match_identity(implementation, analysis_implementation))
        source = condition.get("source_sha256")
        source_match = (isinstance(source, str) and bool(re.fullmatch(r"[0-9a-f]{64}", source))
                        and measured_hashes[language] == source)
        architecture_match = (_norm_arch(host.get("architecture")) is not None
                              and _norm_arch(host["architecture"]) == _norm_arch(condition.get("architecture")))
        measured_options = host["compile"].get(language)
        analysis_options = condition.get("options")
        options_match = isinstance(measured_options, list) and measured_options == analysis_options
        coverage, coverage_match = _coverage(provenance, language)
        checks = {
            "source": bool(source_match), "runtime": runtime_match,
            "implementation": implementation_match, "architecture": architecture_match,
            "options": options_match, "order_coverage": coverage_match,
        }
        rows.append({
            "language": language,
            "measurement_source_sha256": measured_hashes[language],
            "analysis_source_sha256": source,
            "analysis_condition_sha256": hashlib.sha256(
                json.dumps(condition, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "measurement_runtime": runtime,
            "analysis_runtime": analysis_runtime,
            "measurement_implementation": implementation,
            "analysis_implementation": analysis_implementation,
            "measurement_architecture": host.get("architecture"),
            "analysis_architecture": condition.get("architecture"),
            "measurement_options": measured_options,
            "analysis_options": analysis_options,
            "measurement_order": measurement.get("plan"),
            "analysis_order_coverage": coverage,
            "analysis_findings": entry.get("findings"),
            "analysis_evidence": entry.get("evidence"),
            "analysis_evidence_sha256": {
                Path(item["path"]).name: provenance["evidence_sha256"].get(Path(item["path"]).name)
                for item in entry.get("evidence", [])
            },
            "checks": checks,
            "source_exact_match": bool(source_match),
            "runtime_match": runtime_match,
            "implementation_match": implementation_match,
            "architecture_match": architecture_match,
            "options_match": options_match,
            "order_coverage_match": coverage_match,
            "exact_applicability": all(checks.values()),
            "applicability_reasons": [name for name, matched in checks.items() if not matched],
            "impact": "unknown" if not source_match else "not_assessed",
        })
    return {
        "schema_version": "2.0", "issue": 68,
        "analysis_id": analysis["analysis_id"],
        "analysis_code_sha": provenance["code_sha"],
        "measurement_identity": identity,
        "measurement_series_id": measurement["series_id"],
        "measurement_git_sha": measurement["measurement_git_sha"],
        "analysis_trace_options": provenance.get("trace_options"),
        "analysis_evidence_sha256": provenance.get("evidence_sha256"),
        "javascript_orders": provenance.get("javascript_orders"),
        "trace_is_benchmark": provenance["trace_is_benchmark"],
        "causal_conclusion": "not_established",
        "languages": rows,
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Issue #68 PR-B: Windows 実機解析と PR #67 の条件照合", "",
        f"- analysis ID: `{result['analysis_id']}`",
        f"- analysis code SHA: `{result['analysis_code_sha']}`",
        f"- measurement series: `{result['measurement_series_id']}`",
        f"- measurement Git SHA: `{result['measurement_git_sha']}`",
        f"- measurement manifest SHA-256: `{result['measurement_identity']['actual']['sha256']}`",
        f"- trace flags: `{json.dumps(result['analysis_trace_options'])}`", "",
        "| language | source | runtime | implementation | architecture | options | both orders | exact |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["languages"]:
        checks = row["checks"]
        values = ["yes" if checks[key] else "no" for key in
                  ("source", "runtime", "implementation", "architecture", "options", "order_coverage")]
        lines.append(f"| {row['language']} | " + " | ".join(values) +
                     f" | {'yes' if row['exact_applicability'] else 'no'} |")
    lines += ["", "## 言語別条件と所見", ""]
    for row in result["languages"]:
        lines += [
            f"### {row['language']}", "",
            f"- source SHA-256: measurement `{row['measurement_source_sha256']}`; analysis `{row['analysis_source_sha256']}`",
            f"- analysis condition SHA-256 (canonical sorted JSON): `{row['analysis_condition_sha256']}`",
            f"- runtime: measurement `{row['measurement_runtime']}`; analysis `{row['analysis_runtime']}`",
            f"- implementation: measurement `{row['measurement_implementation']}`; analysis `{row['analysis_implementation']}`",
            f"- architecture: measurement `{row['measurement_architecture']}`; analysis `{row['analysis_architecture']}`",
            f"- options: measurement `{row['measurement_options']}`; analysis `{row['analysis_options']}`",
            f"- measurement order: `{row['measurement_order']}`",
            f"- analysis order coverage: `{row['analysis_order_coverage']}`",
            f"- findings: `{row['analysis_findings']}`",
            f"- evidence: `{row['analysis_evidence']}`",
            f"- evidence SHA-256: `{row['analysis_evidence_sha256']}`",
            f"- applicability reasons: `{row['applicability_reasons']}`",
            f"- source mismatch impact: `{row['impact']}`", "",
        ]
    lines += [
        "Python の解析条件 `optimize=0` と測定 manifest の空 options は、"
        "正規化の根拠が公開資料にないため不一致として扱う。", "",
        "PR #67 の測定 manifest には V8 implementation/version が独立した値としてない。"
        "Node.js version 一致から V8 一致を推定しない。", "",
        "JavaScript の trace は性能本測定ではない。条件と観測結果の並置は、最適化が性能差を"
        "生じさせたという因果関係を示さない。source が一致しない場合の影響は unknown とする。", "",
    ]
    return "\n".join(lines)


def publish_outputs(json_output: Path, markdown_output: Path, result: dict) -> None:
    if json_output.parent != markdown_output.parent or json_output == markdown_output:
        raise ValueError("outputs must be distinct files in one new directory")
    destination = json_output.parent
    if destination.exists() or not destination.parent.is_dir():
        raise FileExistsError(f"output directory already exists or parent is missing: {destination}")
    temporary = destination.parent / f".comparison-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        (temporary / json_output.name).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temporary / markdown_output.name).write_text(render_markdown(result), encoding="utf-8")
        if destination.exists():
            raise FileExistsError(f"output directory already exists: {destination}")
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_package", type=Path)
    parser.add_argument("measurement_manifest", type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    if args.expected_sha.lower() != ANALYSIS_CODE_SHA:
        raise SystemExit("unexpected analysis code SHA")
    errors = validate_package(args.analysis_package, ANALYSIS_CODE_SHA)
    if errors:
        raise SystemExit("analysis package validation failed:\n" + "\n".join(errors))
    measurement_bytes = args.measurement_manifest.read_bytes()
    measurement = json.loads(measurement_bytes)
    analysis = json.loads((args.analysis_package / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((args.analysis_package / "provenance.json").read_text(encoding="utf-8"))
    result = build_comparison(measurement, analysis, provenance,
                              hashlib.sha256(measurement_bytes).hexdigest())
    publish_outputs(args.json_output, args.markdown_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
