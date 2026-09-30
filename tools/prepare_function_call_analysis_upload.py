#!/usr/bin/env python3
"""Build an inspected upload copy; leave raw failure evidence on the runner."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from check_function_call_artifact_safety import issues, redact, scan


def prepare(raw: Path, bundle: Path) -> dict:
    if bundle.exists():
        raise ValueError("upload bundle already exists")
    bundle.mkdir(parents=True)
    included: list[str] = []
    excluded: list[dict[str, str]] = []
    redacted: list[str] = []
    files: list[dict] = []
    raw_status = "missing"
    if (raw / "run-state.json").is_file():
        try:
            raw_status = json.loads((raw / "run-state.json").read_text(encoding="utf-8"))["status"]
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            raw_status = "unreadable"
    if raw.is_dir():
        for path in sorted(raw.rglob("*")):
            relative = path.relative_to(raw)
            name = relative.as_posix()
            if path.is_symlink():
                excluded.append({"file": name, "reason": "symbolic link"})
                continue
            if not path.is_file():
                continue
            try:
                original = path.read_bytes()
            except OSError:
                excluded.append({"file": name, "reason": "unreadable"})
                continue
            raw_hash = hashlib.sha256(original).hexdigest()
            try:
                content = original.decode("utf-8")
            except UnicodeError:
                excluded.append({"file": name, "reason": "non-UTF-8", "raw_sha256": raw_hash})
                continue
            content, counts = redact(content)
            problems = issues(content)
            if problems:
                excluded.append({"file": name, "reason": ", ".join(problems), "raw_sha256": raw_hash})
                continue
            sanitized = content.encode("utf-8") if counts else original
            if counts:
                redacted.append(name)
            target = bundle / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(sanitized)
            included.append(name)
            files.append({"file": name, "raw_sha256": raw_hash,
                          "upload_sha256": hashlib.sha256(sanitized).hexdigest(),
                          "redactions": counts})
    report = {
        "schema_version": "1.0",
        "raw_status": raw_status,
        "bundle_status": "complete" if not excluded and not redacted and raw_status == "success" else "partial",
        "included_files": included,
        "excluded_files": excluded,
        "redacted_files": redacted,
        "files": files,
        "raw_kept_separate_from_upload": True,
    }
    (bundle / "upload-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = scan(bundle)
    if errors:
        raise ValueError("upload bundle did not pass final safety scan")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    report = prepare(args.raw, args.bundle)
    print(f"upload_bundle={report['bundle_status']} included={len(report['included_files'])} excluded={len(report['excluded_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
