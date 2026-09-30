#!/usr/bin/env python3
"""Validate an unpublished function-call analysis package before publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from validate_result_json import validate_analysis_manifest

FILES = {"gcc-optimization.txt", "main.s", "python-bytecode.txt", "v8-optimization.txt", "manifest.json"}


def validate_package(root: Path, expected_sha: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"analysis package cannot be read: {exc}"]
    required = {"schema_version", "analysis_id", "code_sha", "generated_at", "operating_system",
                "architecture", "measurement_orders", "trace_is_benchmark", "evidence_sha256"}
    if not isinstance(provenance, dict) or set(provenance) != required:
        return ["provenance fields are invalid"]
    if provenance["schema_version"] != "1.0" or provenance["analysis_id"] != manifest.get("analysis_id"):
        errors.append("provenance identity does not match the analysis manifest")
    code_sha = provenance["code_sha"]
    if not isinstance(code_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        errors.append("code_sha is invalid")
    elif expected_sha is not None and code_sha != expected_sha.lower():
        errors.append("code_sha does not match the trusted main SHA")
    if provenance["measurement_orders"] != ["direct_first", "function_call_first"]:
        errors.append("both measurement orders must be recorded")
    if provenance["trace_is_benchmark"] is not False:
        errors.append("trace execution must not be represented as a benchmark")
    hashes = provenance["evidence_sha256"]
    if not isinstance(hashes, dict) or set(hashes) != FILES:
        errors.append("evidence hash inventory is invalid")
    else:
        for name, expected in hashes.items():
            path = root / name
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                errors.append(f"invalid SHA-256 for {name}")
            elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append(f"evidence was modified or is missing: {name}")
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
