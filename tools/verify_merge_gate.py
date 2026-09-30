#!/usr/bin/env python3
"""Validate GitHub API data before dispatching the local-main sync job."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")


def verify(repository: str, ref: str, target_sha: str, pulls: object, compare_status: str) -> dict:
    if repository != "tetsujisugimori-coder/LangBench-Live" or ref != "refs/heads/main" or not SHA.fullmatch(target_sha):
        raise ValueError("unexpected repository, ref, or target SHA")
    if not isinstance(pulls, list):
        raise ValueError("pull API response must be an array")
    candidates = []
    for pull in pulls:
        if not isinstance(pull, dict):
            raise ValueError("pull API entry must be an object")
        base = pull.get("base") or {}; base_repo = base.get("repo") or {}
        head = pull.get("head") or {}
        if (pull.get("merged_at") is not None and base.get("ref") == "main"
                and base_repo.get("full_name") == repository and SHA.fullmatch(str(pull.get("merge_commit_sha", "")))):
            candidates.append({"pr_number": pull.get("number"), "pr_head_sha": head.get("sha"),
                               "merge_sha": pull["merge_commit_sha"], "target_sha": target_sha})
    if len(candidates) != 1:
        raise ValueError("exactly one merged PR candidate is required")
    result = candidates[0]
    if type(result["pr_number"]) is not int or result["pr_number"] < 1 or not SHA.fullmatch(str(result["pr_head_sha"] or "")):
        raise ValueError("candidate PR identity is invalid")
    # GitHub reports normal/squash/rebase results through merge_commit_sha. It must equal
    # target or be an ancestor according to the compare API; every other status stops.
    if compare_status not in ("identical", "ahead"):
        raise ValueError("merge result is not known to be contained in target main")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True); parser.add_argument("--ref", required=True)
    parser.add_argument("--target-sha", required=True); parser.add_argument("--pulls", type=Path, required=True)
    parser.add_argument("--compare-status", required=True)
    args = parser.parse_args()
    pulls = json.loads(args.pulls.read_text(encoding="utf-8"))
    print(json.dumps(verify(args.repository, args.ref, args.target_sha, pulls, args.compare_status), separators=(",", ":")))
    return 0


if __name__ == "__main__": raise SystemExit(main())
