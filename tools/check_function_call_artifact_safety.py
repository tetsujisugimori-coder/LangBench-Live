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
    # URL slashes are excluded by the leading boundary. Ambiguous slash tokens
    # are resolved from their command/source context below.
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


JS_LITERAL = re.compile(r"^/(?:\\.|[^/\\\r\n])+/[dgimsuvy]*(?=[,;)}\].])")
COMMAND_LINE = re.compile(r"(?:cl(?:\s+/(?:O2|EHsc))+\s+\w+\.\w+|option\s+/quiet)\s*$", re.I)
JS_SOURCE_CONTEXT = re.compile(
    r"(?:\b(?:const|let|var)\s+\w+\s*=\s*|\breturn\s+|\bif\s*\(\s*|"
    r"\[\s*|,\s*|\{\s*\w+\s*:\s*)$"
)
JS_TRACE_FILES = {"v8-optimization-direct_first.txt", "v8-optimization-function_call_first.txt"}


def _safe_slash(content: str, match: re.Match[str], artifact: str | None) -> bool:
    if not match.group().startswith("/") or match.group().startswith("//"):
        return False
    before = content[:match.start()].split("\n")[-1]
    tail = content[match.start():]
    if artifact in JS_TRACE_FILES and JS_LITERAL.match(tail) and JS_SOURCE_CONTEXT.search(before):
        return True
    line = (before + tail.split("\n", 1)[0]).strip()
    return match.group() in {"/O2", "/EHsc", "/quiet"} and bool(COMMAND_LINE.fullmatch(line))


def _matches(content: str, kind: str, artifact: str | None) -> list[re.Match[str]]:
    return [match for match in SENSITIVE[kind].finditer(content)
            if kind != "absolute path" or not _safe_slash(content, match, artifact)]


def issues(content: str, artifact: str | None = None) -> list[str]:
    return [kind for kind in SENSITIVE if _matches(content, kind, artifact)]


def redact(content: str, artifact: str | None = None) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for kind in SENSITIVE:
        matches = _matches(content, kind, artifact)
        for match in reversed(matches):
            content = content[:match.start()] + f"<redacted-{kind.replace(' ', '-')}>" + content[match.end():]
        count = len(matches)
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
        for kind in issues(content, path.relative_to(root).as_posix()):
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
