#!/usr/bin/env python3
"""Authorize Issue #68 PR-A analysis without trusting dispatch inputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def verify(repository: str, ref: str, main_sha: str, pull: dict, run: dict) -> list[str]:
    errors: list[str] = []
    body = pull.get("body") if isinstance(pull.get("body"), str) else ""
    if ref != "refs/heads/main": errors.append("workflow ref is not protected main")
    if pull.get("merged") is not True: errors.append("PR is not merged")
    if pull.get("base", {}).get("ref") != "main": errors.append("PR base is not main")
    if pull.get("base", {}).get("repo", {}).get("full_name") != repository: errors.append("PR repository differs")
    if not re.search(r"(?i)(?:issue\s*)?#\s*68\b", body): errors.append("PR body does not reference Issue #68")
    if not re.search(r"(?i)\bPR[\s-]*A\b", body): errors.append("PR body does not identify PR-A")
    merge_sha = pull.get("merge_commit_sha")
    if not isinstance(merge_sha, str) or merge_sha != main_sha: errors.append("merged PR SHA is not current main")
    if run.get("name") != "Pull local main after verified merge": errors.append("sync workflow differs")
    if run.get("event") != "push" or run.get("head_branch") != "main": errors.append("sync run is not a main push")
    if run.get("head_sha") != main_sha: errors.append("sync run SHA differs")
    if run.get("status") != "completed" or run.get("conclusion") != "success": errors.append("sync run did not succeed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--pull", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    errors = verify(args.repository, args.ref, args.main_sha,
                    json.loads(args.pull.read_text(encoding="utf-8")),
                    json.loads(args.run.read_text(encoding="utf-8")))
    for error in errors: print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
