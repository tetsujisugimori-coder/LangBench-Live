#!/usr/bin/env python3
"""Reject credentials and machine-specific paths in an unpublished analysis artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SENSITIVE = {
    "credential": re.compile(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
        r"Bearer\s+\S+|(?:token|password|secret|authorization)\s*[:=]\s*[^\s\"']+)"
    ),
    # Detect path syntax rather than an allowlist of machine-specific roots.
    # Only complete URLs, generated placeholders, and known command lines
    # may retain ambiguous slash forms below.
    "absolute path": re.compile(
        r"(?ix)(?<![\w/\\])(?:"
        r"file:///(?:[A-Z]:[\\/])?[^\s\"'<>]+"
        r"|(?:\\\\\?\\|\\\\\.\\|\\\\|//)[^\s\"'<>/\\]+[\\/][^\s\"'<>]+"
        r"|[A-Z]:[\\/][^\s\"'<>]*"
        r"|\\/(?!\\/)[\w.~-][^\s\"'<>/\\]*(?:\\/[^\s\"'<>/\\]+)*"
        r"|\\(?!\\)[\w.~-][^\s\"'<>/\\]*(?:\\[^\s\"'<>/\\]+)*"
        r"|/(?!/)[\w.~-][^\s\"'<>/\\]*(?:/[^\s\"'<>/\\]+)*"
        r")"
    ),
}


COMMAND_LINE = re.compile(r"(?:cl(?:\s+/(?:O2|EHsc))+\s+\w+\.\w+|option\s+/quiet)\s*$", re.I)
URL_PREFIX = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:$")
PLACEHOLDER_PREFIX = re.compile(
    r"<(?:checkout|analysis-package|shared-repository|redacted-(?:credential|absolute-path))>$"
)


class DuplicateJsonKey(ValueError):
    """JSON object contains a key that would disappear during parsing."""


def _safe_slash(content: str, match: re.Match[str]) -> bool:
    if not match.group().startswith("/"):
        return False
    before = content[:match.start()].split("\n")[-1]
    tail = content[match.start():]
    if match.group().startswith("//") and URL_PREFIX.search(before):
        return True
    if PLACEHOLDER_PREFIX.search(before):
        return True
    line = (before + tail.split("\n", 1)[0]).strip()
    return match.group() in {"/O2", "/EHsc", "/quiet"} and bool(COMMAND_LINE.fullmatch(line))


def _matches(content: str, kind: str) -> list[re.Match[str]]:
    return [match for match in SENSITIVE[kind].finditer(content)
            if kind != "absolute path" or not _safe_slash(content, match)]


def _text_issues(content: str) -> list[str]:
    return [kind for kind in SENSITIVE if _matches(content, kind)]


def _redact_text(content: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for kind in SENSITIVE:
        matches = _matches(content, kind)
        for match in reversed(matches):
            content = content[:match.start()] + f"<redacted-{kind.replace(' ', '-')}>" + content[match.end():]
        count = len(matches)
        if count:
            counts[kind] = count
    return content, counts


def _parsed_json(content: str) -> tuple[bool, object]:
    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        seen: set[str] = set()
        for key, child in pairs:
            folded = key.casefold()
            if folded in seen:
                raise DuplicateJsonKey("duplicate JSON key")
            seen.add(folded)
            value[key] = child
        return value

    try:
        return True, json.loads(content, object_pairs_hook=reject_duplicate)
    except DuplicateJsonKey:
        raise
    except (ValueError, TypeError):
        return False, None


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _strings(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def issues(content: str) -> list[str]:
    try:
        parsed, value = _parsed_json(content)
    except DuplicateJsonKey:
        return ["duplicate JSON key"]
    if not parsed:
        return _text_issues(content)
    found = {kind for item in _strings(value) for kind in _text_issues(item)}
    return [kind for kind in SENSITIVE if kind in found]


def redact(content: str) -> tuple[str, dict[str, int]]:
    parsed, value = _parsed_json(content)
    if not parsed:
        return _redact_text(content)
    counts: dict[str, int] = {}

    def sanitize(item: object) -> object:
        if isinstance(item, str):
            result, local = _redact_text(item)
            for kind, count in local.items():
                counts[kind] = counts.get(kind, 0) + count
            return result
        if isinstance(item, list):
            return [sanitize(child) for child in item]
        if isinstance(item, dict):
            cleaned: dict[str, object] = {}
            for key, child in item.items():
                safe_key = sanitize(key)
                base_key = safe_key
                suffix = len(cleaned)
                while safe_key.casefold() in {existing.casefold() for existing in cleaned}:
                    safe_key = f"{base_key}-{suffix}"
                    suffix += 1
                cleaned[safe_key] = sanitize(child)
            return cleaned
        return item

    cleaned = sanitize(value)
    if not counts:
        return content, {}
    return json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", counts


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
