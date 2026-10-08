"""Frozen actual main() from 82d4d0ab8212b4025610fc3d16a85b92176a907d.
Only imports supplied; body is byte-for-byte GitHub updater v1, not a simulated v2 guard.
"""
import argparse
import json
import os
from pathlib import Path
from tools.automation_dashboard import REPOSITORY
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(".github/automation-dashboard.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if type(config.get("schema_version")) is not int or config.get("schema_version") != 1 or config.get("repository") != REPOSITORY or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("Unexpected repository/config schema")
    api = GitHub(os.environ["GH_TOKEN"])
    failed = False
    for key, policy in config["issues"].items():
        issue = int(key)
        try:
            print(f"Issue #{issue}: {reconcile(api, issue, policy, datetime.now(timezone.utc).isoformat())}")
        except (ValueError, KeyError, TypeError, urllib.error.URLError, zipfile.BadZipFile) as exc:
            failed = True
            # Never print response bodies, signed URLs, secret values or private paths.
            reason = str(exc) if isinstance(exc, WorkRecordError) else "trusted facts/state unavailable"
            print(f"::error::Issue #{issue}: {reason}; gates fail closed")
            try:
                safe_stop(api, issue, policy)
            except (ValueError, KeyError, TypeError, urllib.error.URLError):
                print(f"::error::Issue #{issue}: Dashboard write unavailable; no success certified")
        # Separate shared preparation transport: a preparation failure cannot
        # mutate Gate evidence or manufacture a Work result/dispatch receipt.
        try:
            try:
                from tools.preparation_github import reconcile_preparation
            except ModuleNotFoundError:
                from preparation_github import reconcile_preparation
            preparation_result = reconcile_preparation(api, issue, policy, datetime.now(timezone.utc).isoformat())
            print(f"Issue #{issue} preparation: {preparation_result}")
        except (ValueError, KeyError, TypeError, urllib.error.URLError):
            failed = True
            print(f"::error::Issue #{issue}: preparation unavailable/unknown; no preparation success certified")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
