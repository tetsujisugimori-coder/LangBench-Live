#!/usr/bin/env python3
"""Observe GitHub REST facts and reconcile configured Issue comments.

Runs only trusted main code. The token can update/create Issue comments, but
no API method for dispatch, rerun, cancellation, merge or Issue close exists.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import zipfile

try:
    from tools.automation_dashboard import (BOT, REPOSITORY, author_matches, evaluate,
                                          parse_state, render, result,
                                          validated_work_record, WorkRecordError, repair_handoff, observed_pr_facts)
except ModuleNotFoundError:
    from automation_dashboard import (BOT, REPOSITORY, author_matches, evaluate,
                                     parse_state, render, result,
                                     validated_work_record, WorkRecordError, repair_handoff, observed_pr_facts)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        destination = urlparse(newurl)
        if destination.scheme != "https":
            raise ValueError("Non-HTTPS artifact redirect refused")
        host = destination.hostname or ""
        if not (host == "api.github.com" or host.endswith(".githubusercontent.com")
                or host.endswith(".blob.core.windows.net") or host == "github-cloud.s3.amazonaws.com"):
            raise ValueError("Unexpected artifact redirect host")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if host != "api.github.com":
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, token=None, sync_artifact_zip=None):
        self.sync_artifact_zip = Path(sync_artifact_zip) if sync_artifact_zip is not None else None
        self.token = token
        self.sync_artifacts = {}
        self.root = f"/repos/{REPOSITORY}"

    def request(self, path, method="GET", data=None, raw=False):
        if not path.startswith(self.root + "/"):
            raise ValueError("Unexpected API destination")
        if method != "GET" and not (method in {"POST", "PATCH"} and "/issues/" in path and "comments" in path):
            raise ValueError("Only Dashboard comment writes are supported")
        if method != "GET" and not self.token:
            raise ValueError("GitHub comment writes require the configured token")
        return self._send_request(path, method, data, raw)

    def _send_request(self, path, method, data, raw=False):
        """Transport only; callers must apply their explicit destination policy."""
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request("https://api.github.com" + path, data=body, method=method,
                                     headers={**({"Authorization": f"Bearer {self.token}"} if self.token else {}), "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        with urllib.request.build_opener(SafeRedirect()).open(req, timeout=30) as response:
            value = response.read(2_000_001)
        if len(value) > 2_000_000:
            raise ValueError("API response exceeds safe bound")
        return value if raw else json.loads(value)

    def get(self, suffix):
        return self.request(self.root + suffix)

    def pages(self, suffix, key=None):
        values = []
        for page in range(1, 101):
            data = self.get(suffix + ("&" if "?" in suffix else "?") + f"per_page=100&page={page}")
            batch = data[key] if key else data
            if not isinstance(batch, list):
                raise ValueError("API pagination shape is invalid")
            values.extend(batch)
            if len(batch) < 100:
                return values
        raise ValueError("API pagination limit reached; completeness is unknown")

    def sync_report(self, run):
        # Inert bounded JSON from a verified main workflow only. No extraction,
        # checkout, importing or execution of artifact contents.
        artifacts = self.pages(f'/actions/runs/{run["id"]}/artifacts', "artifacts")
        name = f'local-main-sync-{run["id"]}-attempt{run["run_attempt"]}'
        items = [a for a in artifacts if a.get("name") == name and a.get("expired") is False]
        if len(items) != 1:
            return None
        artifact = items[0]
        if self.sync_artifact_zip is None:
            data = self.request(self.root + f'/actions/artifacts/{artifact["id"]}/zip', raw=True)
        else:
            # Supported plugin/UI download supplies bytes only. Identity and
            # freshness still come from current API facts, never the local file.
            ident = artifact.get('id')
            if type(ident) is not int or ident <= 0:
                raise ValueError('Current artifact ID unavailable')
            metadata = self.get(f'/actions/artifacts/{ident}')
            if (metadata.get('id') != ident or type(metadata.get('id')) is not int
                    or metadata.get('name') != name or metadata.get('expired') is not False
                    or (metadata.get('workflow_run') or {}).get('id') != run['id']
                    or metadata.get('digest') != artifact.get('digest')):
                raise ValueError('Provided ZIP current artifact/run/attempt identity mismatch')
            with self.sync_artifact_zip.open('rb') as handle:
                data = handle.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('Provided ZIP exceeds safe bound')
        if artifact.get("digest") != "sha256:" + hashlib.sha256(data).hexdigest():
            raise ValueError("Sync artifact digest mismatch or missing")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != "sync-report.json" or entries[0].file_size > 65536 or entries[0].flag_bits & 1:
                raise ValueError("Unexpected sync artifact layout")
            report = json.loads(archive.read(entries[0]).decode("utf-8-sig"))
        self.sync_artifacts[str(run['id'])] = {
            'artifact_id': artifact['id'], 'name': name, 'digest': artifact['digest'], 'zip_verified': True,
            'evidence_url': f'https://github.com/{REPOSITORY}/actions/runs/{run["id"]}/artifacts/{artifact["id"]}'}
        return report


def references(body, issue):
    import re
    return re.search(rf"(?m)^Refs #{issue}\s*$", body or "") is not None


def select_dashboard(comments, policy):
    configured = policy.get("dashboard_comment_id")
    if configured is not None:
        candidates = [c for c in comments if c["id"] == configured]
    else:
        candidates = [c for c in comments if c.get("body", "").startswith("## LangBench-Live Automation Dashboard")
                      and (author_matches(c.get("user"), policy["owner"]) or author_matches(c.get("user"), BOT))]
    if len(candidates) > 1 or (configured is not None and len(candidates) != 1):
        raise ValueError("Dashboard identity is missing or ambiguous")
    if candidates and not (author_matches(candidates[0].get("user"), policy["owner"]) or author_matches(candidates[0].get("user"), BOT)):
        raise ValueError("Dashboard author is not trusted")
    return candidates[0] if candidates else None


def collect(api, issue, policy, previous, include_preparation=True):
    comments = api.pages(f"/issues/{issue}/comments")
    dashboard = select_dashboard(comments, policy)
    comments = [c for c in comments if not dashboard or c["id"] != dashboard["id"]]
    issue_record = api.get(f"/issues/{issue}")
    if "pull_request" in issue_record:
        raise ValueError("Configured Issue is a PR")
    handoff = repair_handoff(comments, previous, issue, policy)
    if handoff:
        prior = api.get(f'/pulls/{handoff["previous_state"]["pr"]}')
        archived = handoff["previous_state"]
        if (prior.get("merged") is not True or prior.get("merge_commit_sha") != archived["merge_sha"]
                or prior.get("head", {}).get("sha") != archived["head_sha"]
                or (prior.get("base", {}).get("repo") or {}).get("full_name") != REPOSITORY
                or prior["base"].get("ref") != "main"):
            raise ValueError("Previous PR API identity changed")
        pull = api.get(f'/pulls/{handoff["repair_pr"]}')
        if not references(pull.get("body"), issue):
            raise ValueError("Repair PR must reference the same Issue")
    elif previous and previous["pr"]:
        pull = api.get(f'/pulls/{previous["pr"]}')
    else:
        pulls = api.pages("/pulls?state=all&sort=updated&direction=desc")
        candidates = [p for p in pulls if references(p.get("body"), issue)
                      and (p.get("base", {}).get("repo") or {}).get("full_name") == REPOSITORY
                      and p.get("base", {}).get("ref") == "main"]
        if len(candidates) > 1:
            raise ValueError("Multiple linked PRs; explicit binding is required")
        pull = api.get(f'/pulls/{candidates[0]["number"]}') if candidates else None
    facts = {"pr": pull, "issue_comments": comments, "pr_comments": [], "reviews": [],
             "ci_runs": [], "sync_runs": [], "jobs": {}, "sync_reports": {},
             "workflow_ids": {}, "condition_runs": {}, "condition_artifacts": {},
             "result_pr": None, "dashboard_comment_id": dashboard["id"] if dashboard else None}
    if include_preparation and 'preparation_contract' in policy:
        try:
            from tools.preparation_github import collect_preparation_gate
        except ModuleNotFoundError:
            from preparation_github import collect_preparation_gate
        facts['preparation_gate'] = collect_preparation_gate(api, issue, policy)
    if not pull:
        return dashboard, facts
    number = pull["number"]
    facts["pr_comments"] = api.pages(f"/issues/{number}/comments")
    facts["reviews"] = api.pages(f"/pulls/{number}/reviews")
    workflows = api.pages("/actions/workflows", "workflows")
    for filename in ("python-tests.yml", "pull-local-main.yml", "measurement-validation-windows.yml", "function-call-analysis-windows.yml"):
        matches = [w for w in workflows if w.get("path") == ".github/workflows/" + filename and w.get("state") == "active"]
        if len(matches) != 1:
            raise ValueError("Official workflow is missing or ambiguous")
        facts["workflow_ids"][filename] = matches[0]["id"]
    facts["ci_runs"] = api.pages("/actions/workflows/python-tests.yml/runs?event=pull_request", "workflow_runs")
    if pull.get("merged"):
        facts["sync_runs"] = api.pages("/actions/workflows/pull-local-main.yml/runs?branch=main", "workflow_runs")
    head = pull["head"]["sha"]
    merge = pull.get("merge_commit_sha") if pull.get("merged") else None
    for run in facts["ci_runs"] + facts["sync_runs"]:
        if run.get("head_sha") not in {head, merge}:
            continue
        facts["jobs"][str(run["id"])] = api.pages(f'/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs', "jobs")
        if (run in facts["sync_runs"] and run.get("head_sha") == merge and run.get("conclusion") == "success"
                and run.get("path") == ".github/workflows/pull-local-main.yml"
                and run.get("workflow_id") == facts["workflow_ids"]["pull-local-main.yml"]
                and run.get("head_branch") == "main" and run.get("event") in {"push", "workflow_dispatch"}
                and (run.get("repository") or {}).get("full_name") == REPOSITORY
                and (run.get("head_repository") or {}).get("full_name") == REPOSITORY):
            facts["sync_reports"][str(run["id"])] = api.sync_report(run)
    # Only trusted reports may select extra public API IDs; values are validated
    # before interpolation. They still cannot grant PASS without fresh API facts.
    records = [validated_work_record(comment, issue, number, policy) for comment in facts['pr_comments']]
    if policy.get('manual_review'):
        try:
            from tools.i01_management import manual_review_records
        except ModuleNotFoundError:
            from i01_management import manual_review_records
        records.extend(value for _, value in manual_review_records(facts['reviews'], issue, number, policy))
    for record in records:
        if record is None or record["head_sha"] != head:
            continue
        for condition in record["conditions"].values():
            for field in ("run_id", "artifact_id", "pr"):
                ident = condition.get(field)
                if type(ident) is not int or ident <= 0:
                    continue
                if field == "run_id":
                    facts["condition_runs"][str(ident)] = api.get(f"/actions/runs/{ident}")
                elif field == "artifact_id":
                    facts["condition_artifacts"][str(ident)] = api.get(f"/actions/artifacts/{ident}")
                else:
                    facts["result_pr"] = api.get(f"/pulls/{ident}")
    return dashboard, facts


def fingerprint(facts):
    return json.dumps(facts, sort_keys=True, separators=(",", ":"))


def reconcile(api, issue, policy, now):
    """Repository workflow concurrency + double collection + post-write check.

    GitHub comments provide no conditional PATCH. Double collection reduces the
    write race, but cannot eliminate it. Re-fetch every Gate fact after writing;
    a detected change is repaired fail-closed in the same comment. Events cover
    later changes, with explicit API/event/queue observation latency.
    """
    comments = api.pages(f"/issues/{issue}/comments")
    dashboard = select_dashboard(comments, policy)
    previous = parse_state(dashboard["body"], issue, policy) if dashboard else None
    for _ in range(3):
        dashboard_before, first = collect(api, issue, policy, previous)
        state = evaluate(issue, policy, previous, first)
        dashboard_after, second = collect(api, issue, policy, previous)
        if fingerprint(first) != fingerprint(second) or dashboard_before != dashboard_after:
            continue
        state["last_updated"] = (previous or {}).get("last_updated")
        observed = observed_pr_facts(issue, policy, second)
        if previous == state and dashboard_after and dashboard_after["body"] == render(state, observed):
            return "NO_OP"
        state["last_updated"] = now
        body = render(state, observed)
        if len(body.encode()) > 60000:
            raise ValueError("Dashboard exceeds safe comment size")
        if dashboard_after:
            saved = api.request(api.root + f'/issues/comments/{dashboard_after["id"]}', "PATCH", {"body": body})
        else:
            # Double collection plus serialized workflow prevents duplicate create.
            saved = api.request(api.root + f"/issues/{issue}/comments", "POST", {"body": body})
        checked_dashboard, checked = collect(api, issue, policy, state)
        expected = copy.deepcopy(second)
        # Creating a Dashboard legitimately changes only its comment identity.
        expected["dashboard_comment_id"] = saved["id"]
        if (fingerprint(checked) != fingerprint(expected) or checked_dashboard is None
                or checked_dashboard["id"] != saved["id"] or checked_dashboard["body"] != body):
            fresh = evaluate(issue, policy, state, checked)
            fresh["current_state"] = "SAFE_STOPPED"
            fresh["merge_gate"] = result("STALE", "Gate facts changed during Dashboard write; fresh event reconciliation required")
            fresh["completion_gate"] = copy.deepcopy(fresh["merge_gate"])
            fresh["last_transition"] = f'{state["current_state"]} -> SAFE_STOPPED'
            fresh["last_updated"] = now
            api.request(api.root + f'/issues/comments/{saved["id"]}', "PATCH", {"body": render(fresh, observed_pr_facts(issue, policy, checked))})
            return "RACE_BLOCKED"
        return "UPDATED"
    raise ValueError("GitHub snapshot changed repeatedly; unsafe to publish")


def safe_stop(api, issue, policy):
    """Preserve unknown/corrupt state and ownership, add an explicit safety stop.

    Do not manufacture a replacement schema or migrate prose PASS on failure.
    The next successful reconciliation replaces this advisory.
    """
    dashboard = select_dashboard(api.pages(f"/issues/{issue}/comments"), policy)
    if not dashboard:
        return
    warning = "\n\n<!-- langbench-dashboard-safe-stop -->\nSAFE_STOPPED — Merge Gate: ERROR; Completion Gate: ERROR. Trusted facts/schema could not be verified.\n"
    body = dashboard["body"].split("\n\n<!-- langbench-dashboard-safe-stop -->")[0]
    try:
        state = parse_state(body, issue, policy)
    except ValueError:
        state = None
    if state:
        state["current_state"] = "SAFE_STOPPED"
        state["merge_gate"] = result("ERROR", "Trusted facts/schema could not be verified")
        state["completion_gate"] = copy.deepcopy(state["merge_gate"])
        body = render(state)
    if dashboard["body"] != body + warning:
        api.request(api.root + f'/issues/comments/{dashboard["id"]}', "PATCH", {"body": body + warning})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(".github/automation-dashboard.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    try:
        from tools.automation_dashboard import validate_policy_config
    except ModuleNotFoundError:
        from automation_dashboard import validate_policy_config
    validate_policy_config(config)
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("Unexpected repository/config schema")
    api = GitHub(os.environ["GH_TOKEN"])
    failed = False
    for key, policy in config["issues"].items():
        issue = int(key)
        try:
            if 'preparation_contract' in policy:
                try:
                    from tools.preparation_github import reconcile_preparation
                except ModuleNotFoundError:
                    from preparation_github import reconcile_preparation
                print(f"Issue #{issue} preparation: {reconcile_preparation(api, issue, policy, datetime.now(timezone.utc).isoformat())}")
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
        if 'preparation_contract' in policy:
            continue
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
