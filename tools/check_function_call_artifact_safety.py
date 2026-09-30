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
    "absolute path": re.compile(r"(?i)(?:[A-Z]:\\|/(?:home|Users|tmp|var)/)[^\s\"'<>]+"),
}


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
        for kind, pattern in SENSITIVE.items():
            if pattern.search(content):
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
