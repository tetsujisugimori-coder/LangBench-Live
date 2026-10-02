"""Measurement manifest v2 construction, validation, and fail-closed comparison."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

LANGUAGES = ("c", "python", "javascript")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
STATES = {"match", "mismatch", "missing", "not_comparable"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_manifest_v2(document: Any) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "measurement_git_sha", "benchmark", "experiment_id",
                "runner", "os", "architecture", "measurement_order", "languages"}
    if not isinstance(document, dict) or set(document) != required:
        return ["measurement manifest v2 root fields are invalid"]
    if document.get("schema_version") != "2.0": errors.append("schema_version must be 2.0")
    if not isinstance(document.get("measurement_git_sha"), str) or not GIT_SHA.fullmatch(document["measurement_git_sha"]): errors.append("measurement_git_sha is invalid")
    for name in ("benchmark", "experiment_id", "os", "architecture"):
        if not isinstance(document.get(name), str) or not document[name].strip(): errors.append(f"{name} is invalid")
    runner = document.get("runner")
    if (not isinstance(runner, dict) or set(runner) != {"path", "sha256"}
            or not isinstance(runner.get("path"), str) or not runner["path"]
            or not isinstance(runner.get("sha256"), str) or not SHA256.fullmatch(runner["sha256"])): errors.append("runner provenance is invalid")
    order = document.get("measurement_order")
    if order not in (["direct", "function_call"], ["function_call", "direct"]): errors.append("measurement_order is invalid")
    languages = document.get("languages")
    if not isinstance(languages, dict) or set(languages) != set(LANGUAGES):
        errors.append("languages are invalid"); return errors
    expected = {
        "c": {"source", "runtime", "compiler", "options"},
        "python": {"source", "runtime", "implementation", "optimize", "options"},
        "javascript": {"source", "runtime", "implementation", "exec_argv", "node_options", "options"},
    }
    for language, entry in languages.items():
        if not isinstance(entry, dict) or set(entry) != expected[language]: errors.append(f"{language} fields are invalid"); continue
        source = entry.get("source")
        if (not isinstance(source, dict) or set(source) != {"path", "sha256"}
                or not isinstance(source.get("path"), str) or not source["path"]
                or not isinstance(source.get("sha256"), str) or not SHA256.fullmatch(source["sha256"])): errors.append(f"{language} source is invalid")
        for identity in ("runtime", "compiler" if language == "c" else "implementation"):
            value = entry.get(identity)
            if not isinstance(value, dict) or set(value) != {"name", "version"} or not all(isinstance(value.get(k), str) and value[k].strip() for k in ("name", "version")): errors.append(f"{language} {identity} is invalid")
        for option in ("options", "exec_argv") if language == "javascript" else ("options",):
            if not isinstance(entry.get(option), list) or not all(isinstance(x, str) for x in entry[option]): errors.append(f"{language} {option} is invalid")
        if language == "python" and (type(entry.get("optimize")) is not int or entry["optimize"] < 0): errors.append("python optimize is invalid")
        if language == "javascript" and not isinstance(entry.get("node_options"), str): errors.append("javascript node_options is invalid")
    return errors


def comparison_state(left: Any, right: Any) -> str:
    if left is None or right is None: return "missing"
    if type(left) is not type(right): return "not_comparable"
    return "match" if left == right else "mismatch"


def compare_conditions(measurement: dict, analysis: dict, language: str) -> dict:
    """Return explicit states; never infer Python optimize or V8 from other fields."""
    measured = measurement.get("languages", {}).get(language, {})
    source = measured.get("source", {}) if isinstance(measured, dict) else {}
    checks = {
        "source_sha256": comparison_state(source.get("sha256"), analysis.get("source_sha256")),
        "architecture": comparison_state(measurement.get("architecture"), analysis.get("architecture")),
        "options": comparison_state(measured.get("options"), analysis.get("options")),
    }
    if language == "javascript": checks["node"] = comparison_state(measured.get("runtime"), analysis.get("runtime")); checks["v8"] = comparison_state(measured.get("implementation"), analysis.get("implementation"))
    elif language == "python":
        checks["implementation"] = comparison_state(measured.get("implementation"), analysis.get("implementation")); checks["optimize"] = comparison_state(measured.get("optimize"), analysis.get("optimize"))
    else: checks["compiler"] = comparison_state(measured.get("compiler"), analysis.get("implementation"))
    return {"checks": checks, "exact_applicability": all(value == "match" for value in checks.values())}
