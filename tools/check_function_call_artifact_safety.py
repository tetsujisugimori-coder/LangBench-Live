#!/usr/bin/env python3
"""Reject credentials and machine-specific paths in an unpublished analysis artifact."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SENSITIVE = {
    "credential": re.compile(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
        r"Bearer\s+\S+|(?:token|password|secret|authorization)\s*[:=]\s*[^\s\"']+)"
    ),
    # Detect path syntax rather than an allowlist of machine-specific roots.
    # URL slashes and JavaScript /regex/ expressions are excluded by the
    # leading and first-segment constraints.
    "absolute path": re.compile(
        r"(?ix)(?<![\w:/\\>])(?:"
        r"file:///(?:[A-Z]:[\\/])?[^\s\"'<>]+"
        r"|(?:\\\\\?\\|\\\\\.\\|\\\\|//)[^\s\"'<>/\\]+[\\/][^\s\"'<>]+"
        r"|[A-Z]:[\\/][^\s\"'<>]*"
        r"|\\(?!\\)[\w.~-][^\s\"'<>/\\]*(?:\\[^\s\"'<>/\\]+)*"
        r"|/(?!/)[\w.~-][^\s\"'<>/\\]*(?:/[^\s\"'<>/\\]+)*"
        r")"
    ),
}


def issues(content: str) -> list[str]:
    return [kind for kind, pattern in SENSITIVE.items() if pattern.search(content)]


def redact(content: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for kind, pattern in SENSITIVE.items():
        content, count = pattern.subn(f"<redacted-{kind.replace(' ', '-')}>", content)
        if count:
            counts[kind] = count
    return content, counts


def scan(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append(f"{path.relative_to(root).as_posix()}: non-UTF-8 artifact")
            continue
        for kind in issues(content):
            errors.append(f"{path.relative_to(root).as_posix()}: {kind}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    errors = scan(args.directory)
    for error in errors:
        print(error)
    if errors:
        return 1
    print("artifact_safety=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
