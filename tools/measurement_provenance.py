"""Measurement manifest v2 validation and fail-closed analysis comparison."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

LANGUAGES = ("c", "python", "javascript")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_capture(document: Any) -> list[str]:
    required = {"schema_version", "experiment_id", "run_ids", "measurement_git_sha", "runners", "sources"}
    if not isinstance(document, dict) or set(document) != required:
        return ["capture fields are invalid"]
    errors = []
    if document.get("schema_version") != "1.0": errors.append("capture schema_version is invalid")
    if not isinstance(document.get("experiment_id"), str) or not document["experiment_id"]: errors.append("capture experiment_id is invalid")
    if not isinstance(document.get("measurement_git_sha"), str) or not GIT_SHA.fullmatch(document["measurement_git_sha"]): errors.append("measurement_git_sha is invalid")
    sources, runners, run_ids = document.get("sources"), document.get("runners"), document.get("run_ids")
    source_items = sources.items() if isinstance(sources, dict) else ()
    runner_items = runners.items() if isinstance(runners, dict) else ()
    for label, value in [*((f"runner {key}", value) for key, value in runner_items), *((f"source {key}", value) for key, value in source_items)]:
        if not isinstance(value, dict) or set(value) != {"path", "sha256"} or not isinstance(value.get("path"), str) or not value["path"] or not isinstance(value.get("sha256"), str) or not SHA256.fullmatch(value["sha256"]): errors.append(f"{label} is invalid")
    if not isinstance(sources, dict) or set(sources) != set(LANGUAGES): errors.append("capture sources are invalid")
    if not isinstance(runners, dict) or set(runners) != {"orchestrator", *LANGUAGES}: errors.append("capture runners are invalid")
    if not isinstance(run_ids, dict) or set(run_ids) != set(LANGUAGES) or not all(isinstance(value, str) and value for value in run_ids.values()): errors.append("capture run_ids are invalid")
    return errors


def validate_manifest_v2(document: Any) -> list[str]:
    required = {"schema_version", "measurement_git_sha", "benchmark", "experiment_id", "run_ids", "runners", "measurement_order", "languages"}
    if not isinstance(document, dict) or set(document) != required: return ["measurement manifest v2 root fields are invalid"]
    errors = []
    capture = {key: document.get(key) for key in ("schema_version", "experiment_id", "run_ids", "measurement_git_sha", "runners")}
    languages_value = document.get("languages")
    capture["schema_version"] = "1.0"; capture["sources"] = {key: value.get("source") if isinstance(value, dict) else None for key, value in languages_value.items()} if isinstance(languages_value, dict) else None
    errors.extend(validate_capture(capture))
    if document.get("schema_version") != "2.0": errors.append("schema_version must be 2.0")
    if not all(isinstance(document.get(k), str) and document[k] for k in ("benchmark", "experiment_id")): errors.append("benchmark or experiment_id is invalid")
    if document.get("measurement_order") not in (["direct", "function_call"], ["function_call", "direct"]): errors.append("measurement_order is invalid")
    languages = document.get("languages")
    if not isinstance(languages, dict) or set(languages) != set(LANGUAGES): return errors + ["languages are invalid"]
    fields = {"c":{"source","os","architecture","runtime","compiler","options"}, "python":{"source","os","architecture","runtime","implementation","optimize","options"}, "javascript":{"source","os","architecture","runtime","implementation","exec_argv","node_options","options"}}
    for language, entry in languages.items():
        if not isinstance(entry, dict) or set(entry) != fields[language]: errors.append(f"{language} fields are invalid"); continue
        for key in ("os", "architecture"):
            if not isinstance(entry.get(key), str) or not entry[key]: errors.append(f"{language} {key} is invalid")
        for key in ("runtime", "compiler" if language == "c" else "implementation"):
            identity = entry.get(key)
            if not isinstance(identity, dict) or set(identity) != {"name","version"} or not all(isinstance(identity.get(x), str) and identity[x] for x in ("name","version")): errors.append(f"{language} {key} is invalid")
        for key in (("options","exec_argv") if language == "javascript" else ("options",)):
            if not isinstance(entry.get(key), list) or not all(isinstance(x, str) for x in entry[key]): errors.append(f"{language} {key} is invalid")
        if language == "python" and (type(entry.get("optimize")) is not int or entry["optimize"] < 0): errors.append("python optimize is invalid")
        if language == "javascript" and not isinstance(entry.get("node_options"), str): errors.append("javascript node_options is invalid")
    return errors


def state(left: Any, right: Any) -> str:
    if left is None or right is None: return "missing"
    if type(left) is not type(right): return "not_comparable"
    return "match" if left == right else "mismatch"


def compare_conditions(measurement: Any, analysis: Any, language: str) -> dict:
    """Compare every exactness prerequisite without normalizing or inferring values."""
    valid = validate_manifest_v2(measurement)
    if not isinstance(analysis, dict): analysis = {}
    languages = measurement.get("languages") if isinstance(measurement, dict) else None
    measured_value = languages.get(language) if isinstance(languages, dict) else None
    measured = measured_value if isinstance(measured_value, dict) else {}
    source_value = measured.get("source")
    source = source_value if isinstance(source_value, dict) else {}
    coverage = analysis.get("order_coverage")
    if coverage is None: order_state = "missing"
    elif not isinstance(coverage, dict): order_state = "not_comparable"
    else:
        confirmed, unconfirmed = coverage.get("confirmed"), coverage.get("unconfirmed")
        expected_basis = "trace_observed" if language == "javascript" else "static_analysis"
        valid_coverage = (coverage.get("basis") == expected_basis and isinstance(confirmed, list)
                          and all(isinstance(value, str) for value in confirmed)
                          and len(confirmed) == len(set(confirmed)) and set(confirmed) == {"direct_first", "function_call_first"}
                          and unconfirmed == [])
        order_state = "match" if valid_coverage else "not_comparable"
    checks = {
        "manifest": "match" if not valid else "not_comparable", "source_sha256": state(source.get("sha256"), analysis.get("source_sha256")),
        "os": state(measured.get("os"), analysis.get("os")), "architecture": state(measured.get("architecture"), analysis.get("architecture")),
        "runtime": state(measured.get("runtime"), analysis.get("runtime")), "options": state(measured.get("options"), analysis.get("options")), "order_coverage": order_state,
    }
    if language == "javascript":
        checks.update(v8=state(measured.get("implementation"), analysis.get("implementation")), exec_argv=state(measured.get("exec_argv"), analysis.get("exec_argv")), node_options=state(measured.get("node_options"), analysis.get("node_options")))
    elif language == "python": checks.update(implementation=state(measured.get("implementation"), analysis.get("implementation")), optimize=state(measured.get("optimize"), analysis.get("optimize")))
    else: checks["compiler"] = state(measured.get("compiler"), analysis.get("implementation"))
    return {"checks": checks, "validation_errors": valid, "exact_applicability": all(value == "match" for value in checks.values())}
