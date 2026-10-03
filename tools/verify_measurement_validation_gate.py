"""Fail-closed authorization for the trusted-main Windows validation workflow."""

import argparse
import json
from pathlib import Path


REPOSITORY = "tetsujisugimori-coder/LangBench-Live"
SYNC_WORKFLOW = ".github/workflows/pull-local-main.yml"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(repository, ref, event, run_sha, main_before, main_after, pulls, runs, jobs):
    errors = []
    if repository != REPOSITORY: errors.append("unexpected repository")
    if ref != "refs/heads/main": errors.append("workflow ref is not main")
    if event != "workflow_dispatch": errors.append("unexpected workflow event")
    if main_before != run_sha or main_after != run_sha: errors.append("main SHA differs or changed during authorization")
    # commits/{sha}/pulls omits merged_by. The workflow hydrates candidates via
    # pulls/{number} before invoking this verifier.
    trusted = [p for p in pulls if p.get("merged_at") and isinstance(p.get("merge_commit_sha"), str)
               and p.get("base", {}).get("ref") == "main"
               and p.get("base", {}).get("repo", {}).get("full_name") == repository
               and p.get("merged_by", {}).get("type") == "User"
               and p.get("target_compare_status") in {"identical", "ahead"}
               and isinstance(p.get("number"), int)]
    if len(trusted) != 1: errors.append("run SHA is not a unique human-merged PR commit")
    candidates = [r for r in runs.get("workflow_runs", [])
                  if r.get("path") == SYNC_WORKFLOW and r.get("head_repository", {}).get("full_name") == repository
                  and r.get("head_branch") == "main" and r.get("head_sha") == run_sha
                  and r.get("event") in {"push", "workflow_dispatch"} and r.get("status") == "completed"
                  and r.get("conclusion") == "success"]
    successful = []
    for run in candidates:
        run_jobs = jobs.get(str(run.get("id")), {}).get("jobs", [])
        by_name = {job.get("name"): job for job in run_jobs}
        if all(by_name.get(name, {}).get("status") == "completed" and
               by_name[name].get("conclusion") == "success" for name in ("verify-merge", "pull-main")):
            successful.append(run)
    if not successful: errors.append("no matching successful official synchronization run and jobs")
    if errors: raise ValueError("; ".join(errors))
    chosen = max(successful, key=lambda r: r["id"])
    return {"trusted_sha": run_sha, "sync_run_id": chosen["id"], "pull_number": trusted[0]["number"]}


def main():
    p = argparse.ArgumentParser()
    for name in ("repository", "ref", "event", "run-sha", "main-before", "main-after"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--pulls", type=Path, required=True); p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--jobs", type=Path, required=True)
    a = p.parse_args()
    try:
        result = verify(a.repository, a.ref, a.event, a.run_sha, a.main_before, a.main_after,
                        load(a.pulls), load(a.runs), load(a.jobs))
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"status": "rejected", "reason": str(e)})); return 1
    print(json.dumps({"status": "authorized", **result})); return 0


if __name__ == "__main__": raise SystemExit(main())
