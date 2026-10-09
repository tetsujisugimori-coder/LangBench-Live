#!/usr/bin/env python3
"""Pure Dashboard state/evidence evaluator. Events are hints, never facts.

Only the API adapter constructs facts. JSON in the Dashboard is a cache, not
an authority for PASS. Dispatch receipts are owner-authenticated audit records;
this module and its caller never dispatch, cancel, rerun, merge or close.
"""
from __future__ import annotations

import copy
import json
import re

REPOSITORY = "tetsujisugimori-coder/LangBench-Live"
SHA = re.compile(r"^[0-9a-f]{40}$")
START = "<!-- langbench-automation-state:v1\n"
END = "\nlangbench-automation-state:end -->"
WORK = "langbench-work-review:v1"
RECEIPT = "langbench-dispatch-receipt:v1"
SMOKE = "langbench-live-smoke:v1"
BOT = {"login": "github-actions[bot]", "id": 41898282, "type": "Bot"}
STATUSES = {"PASS", "PENDING", "BLOCKED", "STALE", "ERROR", "NOT_REQUIRED"}
DISPATCH = {"REQUESTED", "DISPATCHING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"}


def validate_policy_config(config):
    """Version barrier: v1 remains readable; mandatory v2 entries require v2."""
    if (not isinstance(config, dict) or type(config.get('schema_version')) is not int
            or config['schema_version'] not in (1, 2) or config.get('repository') != REPOSITORY
            or not isinstance(config.get('issues'), dict)):
        raise ValueError('Unsupported repository/policy schema')
    for entry in config['issues'].values():
        if not isinstance(entry, dict): raise ValueError('Invalid Issue policy')
        if 'preparation_contract' in entry and (config['schema_version'] != 2
                or type(entry['preparation_contract']) is not int or entry['preparation_contract'] != 2):
            raise ValueError('Mandatory preparation requires policy/reader v2')
        if 'resume_protocol' in entry and (entry.get('preparation_contract') != 2
                or type(entry['resume_protocol']) is not int or entry['resume_protocol'] != 2):
            raise ValueError('Unsupported required I-01 resume protocol')
    for key, entry in config['issues'].items():
        if 'i01_manager' in entry or 'manual_review' in entry:
            try:
                from tools.i01_management import validate_extensions
            except ModuleNotFoundError:
                from i01_management import validate_extensions
            validate_extensions(int(key), entry)
    return config


def sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def author_matches(user, expected):
    return isinstance(user, dict) and all(user.get(k) == expected[k] for k in ("login", "id", "type"))


def envelope(body, marker):
    """One whole, versioned JSON record; never search for PASS in prose."""
    if not isinstance(body, str):
        return None
    match = re.fullmatch(r"\s*<!-- " + re.escape(marker) + r"\s*\n(.*?)\n-->\s*", body, re.S)
    if not match:
        return None
    try:
        value = json.loads(match[1])
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def result(status, reason, **evidence):
    return {"status": status, "reason": reason, **evidence}


def comment_order(comment):
    return (comment.get("updated_at") or comment.get("created_at") or "", comment["id"])


def combine(checks):
    for status in ("ERROR", "BLOCKED", "STALE", "PENDING"):
        reasons = [x["reason"] for x in checks if x["status"] == status]
        if reasons:
            return result(status, "; ".join(reasons))
    return result("PASS", "All required evidence is current and successful")


def dedup_key(issue, receipt):
    return f'{REPOSITORY}:issue{issue}:{receipt["target_sha"]}:{receipt["action_type"]}:{receipt["purpose_id"]}'


def valid_receipt(issue, policy, item):
    return (isinstance(item, dict) and sha(item.get("target_sha"))
            and item.get("action_type") in policy["dispatch_owners"]
            and isinstance(item.get("purpose_id"), str)
            and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", item["purpose_id"]) is not None
            and item.get("dedup_key") == dedup_key(issue, item)
            and item.get("state") in DISPATCH
            and isinstance(item.get("run_id"), str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", item["run_id"]) is not None
            and type(item.get("attempt")) is int and item["attempt"] > 0
            and (item["attempt"] == 1 or isinstance(item.get("retry_of"), str)))


def initial_state(issue, policy):
    required_names = {"windows_validation", "windows_measurement", "artifact_integrity", "measurement_result_pr", "live_smoke"}
    if (set(policy["requirements"]) != required_names
            or any(value not in {"REQUIRED", "NOT_REQUIRED"} for value in policy["requirements"].values())):
        raise ValueError("Unknown or missing requirement policy")
    item = copy.deepcopy(policy["initial_dispatch"])
    if item is not None and not valid_receipt(issue, policy, item):
        raise ValueError("Invalid configured initial dispatch")
    return {
        "schema_version": 1, "repository": REPOSITORY, "issue": issue,
        "purpose": policy["purpose"], "current_state": "IMPLEMENTING" if item else "AUTOMATION_ARMED",
        "current_actor": "Cloud Codex" if item else "Work", "dispatch_owners": copy.deepcopy(policy["dispatch_owners"]),
        "active_action": item["action_type"] if item else None, "purpose_id": item["purpose_id"] if item else None,
        "dedup_key": item["dedup_key"] if item else None, "dispatch_state": item["state"] if item else None,
        "active_run_id": item["run_id"] if item else None, "dispatches": [item] if item else [],
        "pr": None, "head_sha": None, "work_review": result("PENDING", "No current Work review"),
        "required_ci": result("PENDING", "No current CI"), "ci_head_sha": None,
        "ci_ubuntu": result("PENDING", "No current Ubuntu CI"),
        "ci_windows": result("PENDING", "No current Windows CI"),
        "public_data": result("PENDING", "Public data verification is required"),
        "requirements": copy.deepcopy(policy["requirements"]), "conditions": {},
        "merge_state": "PENDING", "merge_sha": None,
        "local_sync": result("PENDING", "Exact merge sync is required"), "local_sync_target_sha": None,
        "blockers": [], "follow_up": [], "follow_up_recorded": False,
        "merge_gate": result("PENDING", "No PR"), "completion_gate": result("PENDING", "Not merged"),
        "last_transition": "AUTOMATION_ARMED -> IMPLEMENTING" if item else "Policy registered; dispatch not started", "last_updated": None,
    }


ACTIVE_FIELDS = ("active_action", "purpose_id", "dedup_key", "dispatch_state", "active_run_id")


def undispatched(state, policy):
    """Only explicitly unstarted policies may have no active receipt.

    Null is an audited policy choice, not a default for missing configuration.
    Never accept a partial identity, lost ledger, bound PR or cached PASS.
    """
    return (policy["initial_dispatch"] is None and state["dispatches"] == []
            and all(state[k] is None for k in ACTIVE_FIELDS)
            and state["current_state"] in {"AUTOMATION_ARMED", "SAFE_STOPPED"}
            and all(state[k] is None for k in ("pr", "head_sha", "merge_sha", "ci_head_sha", "local_sync_target_sha"))
            and state["merge_state"] == "PENDING"
            and all(state[k]["status"] != "PASS" for k in
                    ("work_review", "required_ci", "ci_ubuntu", "ci_windows", "public_data",
                     "local_sync", "merge_gate", "completion_gate"))
            and all(isinstance(v, dict) and v.get("status") != "PASS"
                    for v in state["conditions"].values()))


def parse_state(body, issue, policy):
    if "langbench-automation-state:" not in body:
        return None  # Explicit legacy migration from audited config + fresh API only.
    if body.count(START) != 1 or body.count(END) != 1:
        raise ValueError("Unknown schema or malformed Dashboard marker")
    try:
        state = json.loads(body.split(START)[1].split(END)[0])
    except ValueError as exc:
        raise ValueError("Broken Dashboard JSON") from exc
    template = initial_state(issue, policy)
    if not isinstance(state, dict) or set(state) != set(template):
        raise ValueError("Unknown or missing state fields")
    for key in ("schema_version", "repository", "issue", "purpose", "dispatch_owners", "requirements"):
        if state[key] != template[key] or type(state[key]) is not type(template[key]):
            raise ValueError(f"State/config disagreement: {key}")
    for key in ("head_sha", "merge_sha", "ci_head_sha", "local_sync_target_sha"):
        if state[key] is not None and not sha(state[key]):
            raise ValueError(f"Invalid SHA: {key}")
    if not isinstance(state["dispatches"], list) or not all(valid_receipt(issue, policy, x) for x in state["dispatches"]):
        raise ValueError("Malformed ownership/dedup ledger")
    for key in ("work_review", "required_ci", "ci_ubuntu", "ci_windows", "public_data", "local_sync", "merge_gate", "completion_gate"):
        item = state[key]
        if not isinstance(item, dict) or item.get("status") not in STATUSES or not isinstance(item.get("reason"), str):
            raise ValueError(f"Malformed evidence: {key}")
    for key in ("blockers", "follow_up"):
        if not isinstance(state[key], list):
            raise ValueError(f"Malformed list: {key}")
    if not isinstance(state["conditions"], dict) or type(state["follow_up_recorded"]) is not bool:
        raise ValueError("Malformed conditions/follow-up")
    if (not isinstance(state["current_state"], str) or not isinstance(state["current_actor"], str)
            or not isinstance(state["last_transition"], str)
            or (state["last_updated"] is not None and not isinstance(state["last_updated"], str))
            or (state["pr"] is not None and (type(state["pr"]) is not int or state["pr"] <= 0))
            or not (undispatched(state, policy) or
                    (isinstance(state["dispatch_state"], str) and state["dispatch_state"] in DISPATCH
                     and any(r["dedup_key"] == state["dedup_key"] and r["run_id"] == state["active_run_id"]
                             and r["action_type"] == state["active_action"] and r["purpose_id"] == state["purpose_id"]
                             for r in state["dispatches"])))):
        raise ValueError("Malformed state/active ownership identity")
    return state


class WorkRecordError(ValueError):
    """Authenticated Work evidence has an invalid schema (public reason only)."""


def validated_work_record(comment, issue, pr, policy):
    """Validate before reading conditions or allowing a record to select API IDs.

    Other authors/identities and ordinary prose are not Work evidence. A broken
    record from the configured Work identity is an error, not a missing review
    that permits an older PASS to remain authoritative.
    """
    if not author_matches(comment.get("user"), policy["work_author"]):
        return None
    body = comment.get("body")
    value = envelope(body, WORK)
    if value is None:
        if isinstance(body, str) and body.lstrip().startswith("<!-- langbench-work-review:"):
            raise WorkRecordError("Malformed Work envelope or unknown schema")
        return None
    if (value.get("repository") != REPOSITORY or type(value.get("issue")) is not int
            or value.get("issue") != issue or type(value.get("pr")) is not int or value.get("pr") != pr
            or value.get("automation_id") != policy["work_automation_id"] or value.get("kind") != "work_review"):
        return None
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or not sha(value.get("head_sha")):
        raise WorkRecordError("Invalid Work schema or head identity")
    return validate_work_payload(value)


def validate_work_payload(value):
    if (not isinstance(value.get("blockers"), list) or not isinstance(value.get("follow_up"), list)
            or "active_blocker" not in value or type(value.get("follow_up_recorded")) is not bool
            or not isinstance(value.get("verdict"), str) or value["verdict"] not in {"PASS", "BLOCKED", "PENDING"}):
        raise WorkRecordError("Invalid Work blocker/follow-up/verdict fields")
    conditions = value.get("conditions")
    if not isinstance(conditions, dict):
        raise WorkRecordError("Work conditions must be an object")
    names = {"windows_validation", "windows_measurement", "artifact_integrity", "measurement_result_pr"}
    for name, condition_record in conditions.items():
        if (name not in names or not isinstance(condition_record, dict)
                or not isinstance(condition_record.get("status"), str)
                or condition_record["status"] not in {"PASS", "PENDING", "BLOCKED", "STALE", "ERROR"}
                or not sha(condition_record.get("head_sha"))):
            raise WorkRecordError("Invalid Work condition record")
        for field in ("run_id", "artifact_id", "pr"):
            if field in condition_record and (type(condition_record[field]) is not int or condition_record[field] <= 0):
                raise WorkRecordError("Invalid Work condition API identity")
    return value


def work_review(comments, issue, pr, head, policy, reviews=None):
    accepted = []
    if policy.get('manual_review'):
        try:
            from tools.i01_management import manual_review_records
        except ModuleNotFoundError:
            from i01_management import manual_review_records
        try:
            accepted.extend(manual_review_records(reviews or [], issue, pr, policy))
        except WorkRecordError as exc:
            return result("ERROR", str(exc), head_sha=head), None
    for comment in comments:
        try:
            value = validated_work_record(comment, issue, pr, policy)
        except WorkRecordError as exc:
            return result("ERROR", str(exc), head_sha=head), None
        if value:
            accepted.append((comment_order(comment), value))
    if not accepted:
        return result("PENDING", "Authenticated structured Work review is missing"), None
    current = [x for x in accepted if x[1]["head_sha"] == head]
    if not current:
        return result("STALE", "Work review belongs to a previous head"), None
    order, value = max(current, key=lambda x: x[0])
    ident = order[1]
    if (not isinstance(value.get("blockers"), list) or not isinstance(value.get("follow_up"), list)
            or "active_blocker" not in value or not isinstance(value.get("conditions"), dict)
            or value.get("follow_up_recorded") is not True or value.get("active_blocker") is not None
            or value.get("verdict") not in {"PASS", "BLOCKED", "PENDING"}):
        return result("ERROR", "Work evidence is missing explicit blocker/follow-up fields", head_sha=head), None
    status = "BLOCKED" if value["blockers"] else value["verdict"]
    provenance = value.get('review_provenance', {})
    return result(status, "Authenticated Work review for current head", head_sha=head,
                  comment_id=ident, **provenance), value


def workflow_identity(run, path, workflow_id, repository=REPOSITORY):
    return (run.get("path") == path and run.get("workflow_id") == workflow_id
            and (run.get("repository") or {}).get("full_name") == repository
            and (run.get("head_repository") or {}).get("full_name") == repository
            and type(run.get("id")) is int and type(run.get("run_attempt")) is int)


def run_jobs(run, jobs, names):
    if run.get("status") != "completed":
        return result("PENDING", "Workflow is not completed", run_id=run["id"])
    if run.get("conclusion") != "success":
        return result("BLOCKED", "Workflow did not succeed", run_id=run["id"])
    for name in names:
        found = [j for j in jobs if j.get("name") == name]
        if len(found) != 1 or found[0].get("head_sha") != run.get("head_sha"):
            return result("ERROR", f"Missing/ambiguous job {name}")
        if found[0].get("status") != "completed":
            return result("PENDING", f"Job {name} is pending")
        if found[0].get("conclusion") != "success":
            return result("BLOCKED", f"Job {name} did not succeed")
    return result("PASS", "Official workflow and required jobs succeeded", run_id=run["id"],
                  run_attempt=run["run_attempt"], head_sha=run["head_sha"])


def ci_pr_identity(run, pull, head):
    """Only merged API PRs may lose GitHub's run association list."""
    links = run.get("pull_requests")
    if not isinstance(links, list) or any(not isinstance(p, dict) for p in links):
        return False
    if links:
        return any(p.get("number") == pull["number"] for p in links)
    return (pull.get("merged") is True and pull.get("state") == "closed"
            and sha(pull.get("merge_commit_sha")) and sha(head)
            and pull.get("head", {}).get("sha") == head
            and run.get("head_sha") == head
            and isinstance(pull.get("head", {}).get("ref"), str)
            and bool(pull["head"]["ref"])
            and run.get("head_branch") == pull["head"]["ref"]
            and (pull["head"].get("repo") or {}).get("full_name") == REPOSITORY
            and (pull.get("base", {}).get("repo") or {}).get("full_name") == REPOSITORY
            and pull["base"].get("ref") == "main")


def repair_handoff(comments, previous, issue, policy):
    """Explicit owner acceptance; immutable record retains the previous cycle."""
    records = []
    for comment in sorted(comments, key=comment_order):
        if not author_matches(comment.get("user"), policy["owner"]):
            continue
        body = comment.get("body")
        value = envelope(body, "langbench-pr-handoff:v1")
        if (isinstance(body, str) and body.lstrip().startswith("<!-- langbench-pr-handoff:")
                and value is None):
            raise ValueError("Malformed or unknown owner PR handoff envelope")
        if not value or value.get("repository") != REPOSITORY or value.get("issue") != issue:
            continue
        if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ValueError("Unknown PR handoff schema")
        archived = value.get("previous_state")
        if not isinstance(archived, dict):
            raise ValueError("PR handoff must archive the prior state")
        archived = parse_state(render(archived), issue, policy)
        target = value.get("repair_pr")
        if (type(target) is not int or target <= 0 or target == archived["pr"]
                or archived["merge_state"] != "MERGED" or not sha(archived["merge_sha"])
                or archived["local_sync"].get("status") != "PASS"
                or archived["local_sync"].get("target_sha") != archived["merge_sha"]):
            raise ValueError("Invalid post-merge repair handoff")
        if type(archived["pr"]) is not int or archived["pr"] <= 0:
            raise ValueError("Invalid handoff source PR")
        records.append(value)
    outgoing, incoming = {}, {}
    for value in records:
        source, target = value["previous_state"]["pr"], value["repair_pr"]
        # Even identical records in separate comments are ambiguous ownership.
        if source in outgoing or target in incoming:
            raise ValueError("Ambiguous PR handoff: fork or duplicate record")
        outgoing[source], incoming[target] = value, value
    if records:
        roots = set(outgoing) - set(incoming)
        if len(roots) != 1:
            raise ValueError("Broken PR handoff chain")
        node, seen = next(iter(roots)), set()
        while node in outgoing:
            if node in seen:
                raise ValueError("Cyclic PR handoff chain")
            seen.add(node)
            node = outgoing[node]["repair_pr"]
        if len(seen) != len(records):
            raise ValueError("Disconnected PR handoff chain")
    if not previous:
        return None
    current = previous["pr"]
    # An outgoing transition supersedes the incoming historical receipt.
    selected = outgoing.get(current)
    if selected:
        archived = selected["previous_state"]
        if any(previous[k] != archived[k] for k in
               ("head_sha", "merge_sha", "local_sync", "dispatches")):
            raise ValueError("PR handoff archive does not match current cycle")
        return selected
    return incoming.get(current)


def ci_evidence(facts, head):
    path = ".github/workflows/python-tests.yml"
    candidates = [r for r in facts["ci_runs"]
                  if workflow_identity(r, path, facts["workflow_ids"]["python-tests.yml"])
                  and r.get("event") == "pull_request"
                  and ci_pr_identity(r, facts["pr"], head)]
    current = [r for r in candidates if r.get("head_sha") == head]
    if not current:
        evidence = result("STALE" if candidates else "PENDING", "CI for current head is missing")
        return evidence, copy.deepcopy(evidence), copy.deepcopy(evidence)
    run = max(current, key=lambda r: (r["id"], r["run_attempt"]))
    jobs = facts["jobs"].get(str(run["id"]), [])
    ubuntu = run_jobs(run, jobs, ["python-tests (ubuntu-latest)"])
    windows = run_jobs(run, jobs, ["python-tests (windows-latest)"])
    # Public data tests are in the required unittest-discovery step on both OSs.
    public = combine([ubuntu, windows])
    for job in jobs:
        if job.get("name") in {"python-tests (ubuntu-latest)", "python-tests (windows-latest)"}:
            steps = [s for s in job.get("steps", []) if s.get("name") == "Run python -B -m unittest discover -s tests -q"]
            if len(steps) != 1 or steps[0].get("conclusion") != "success":
                public = result("PENDING", "Public data unittest step has not succeeded")
    return ubuntu, windows, public


def sync_evidence(facts, merge_sha):
    if not sha(merge_sha):
        return result("PENDING", "Human merge is not confirmed")
    runs = [r for r in facts["sync_runs"]
            if workflow_identity(r, ".github/workflows/pull-local-main.yml", facts["workflow_ids"]["pull-local-main.yml"])
            and r.get("head_sha") == merge_sha and r.get("head_branch") == "main"
            and r.get("event") in {"push", "workflow_dispatch"}]
    if not runs:
        return result("PENDING", "No official sync run for exact merge SHA")
    run = max(runs, key=lambda r: (r["id"], r["run_attempt"]))
    check = run_jobs(run, facts["jobs"].get(str(run["id"]), []), ["verify-merge", "pull-main"])
    if check["status"] != "PASS":
        return check
    report = facts["sync_reports"].get(str(run["id"]))
    expected = {"schema_version": 1, "repository": REPOSITORY, "pr": facts["pr"]["number"],
                "pr_head_sha": facts["pr"]["head"]["sha"], "merge_sha": merge_sha,
                "target_sha": merge_sha, "after_sha": merge_sha, "run_id": str(run["id"]),
                "run_attempt": run["run_attempt"], "status": "success", "protected_preserved": True}
    if (not isinstance(report, dict) or any(report.get(k) != v or type(report.get(k)) is not type(v) for k, v in expected.items())
            or not sha(report.get("before_sha")) or type(report.get("protected_files")) is not int or report["protected_files"] < 0):
        return result("ERROR", "Official sync safety report is missing or has a different identity")
    return result("PASS", "Exact merge SHA synchronized; protected files preserved", target_sha=merge_sha,
                  run_id=run["id"], run_attempt=run["run_attempt"])


def condition(name, requirement, report, target, facts):
    if requirement == "NOT_REQUIRED":
        return result("NOT_REQUIRED", "Explicit trusted policy")
    if requirement != "REQUIRED":
        return result("ERROR", f"Unknown/missing requirement: {name}")
    record = (report or {}).get("conditions", {}).get(name)
    if not isinstance(record, dict):
        return result("PENDING", f"Required {name} evidence is missing")
    if record.get("head_sha") != target:
        return result("STALE", f"{name} evidence belongs to a different SHA")
    if record.get("status") != "PASS":
        return result("BLOCKED" if record.get("status") == "BLOCKED" else "PENDING", f"Required {name} is not successful")
    # A trusted Work report must point to a re-fetched successful official run,
    # artifact, or merged result PR. A report's arbitrary PASS alone is insufficient.
    if name == "measurement_result_pr":
        pull = facts.get("result_pr")
        valid = (isinstance(pull, dict) and pull.get("number") == record.get("pr")
                 and pull.get("merged") is True and (pull.get("base", {}).get("repo") or {}).get("full_name") == REPOSITORY
                 and pull.get("base", {}).get("ref") == "main" and sha(pull.get("merge_commit_sha")))
    else:
        run = facts.get("condition_runs", {}).get(str(record.get("run_id")))
        paths = {"windows_validation": ".github/workflows/measurement-validation-windows.yml",
                 "windows_measurement": ".github/workflows/function-call-analysis-windows.yml",
                 "artifact_integrity": ".github/workflows/measurement-validation-windows.yml"}
        path = paths.get(name)
        valid = (path is not None and isinstance(run, dict)
                 and workflow_identity(run, path, facts["workflow_ids"].get(path.rsplit("/", 1)[1]))
                 and run.get("head_sha") == target and run.get("head_branch") == "main"
                 and run.get("event") == "workflow_dispatch" and run.get("conclusion") == "success"
                 and run.get("status") == "completed")
        if name == "artifact_integrity":
            artifact = facts.get("condition_artifacts", {}).get(str(record.get("artifact_id")))
            valid = (valid and isinstance(artifact, dict) and artifact.get("expired") is False
                     and (artifact.get("workflow_run") or {}).get("id") == record.get("run_id")
                     and isinstance(record.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is not None
                     and artifact.get("digest") == "sha256:" + record["sha256"])
    return result("PASS" if valid else "ERROR", f"{name}: authenticated report + GitHub evidence")


def dispatch_ledger(state, comments, issue, policy):
    ledger = {(r["dedup_key"], r["run_id"]): copy.deepcopy(r) for r in state["dispatches"]}
    for comment in sorted(comments, key=comment_order):
        if not author_matches(comment.get("user"), policy["owner"]):
            continue
        value = envelope(comment.get("body"), RECEIPT)
        if not value or value.get("repository") != REPOSITORY or value.get("issue") != issue:
            continue
        item = value.get("dispatch")
        if type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or not valid_receipt(issue, policy, item):
            raise ValueError("Invalid authenticated dispatch receipt")
        ledger[(item["dedup_key"], item["run_id"])] = copy.deepcopy(item)
    return sorted(ledger.values(), key=lambda r: (r["dedup_key"], r["attempt"], r["run_id"]))


def evaluate(issue, policy, previous, facts):
    state = copy.deepcopy(previous or initial_state(issue, policy))
    old_state = state["current_state"]
    handoff = repair_handoff(facts["issue_comments"], previous, issue, policy)
    if handoff and handoff["repair_pr"] == (facts.get("pr") or {}).get("number"):
        state["pr"] = handoff["repair_pr"]
    state["dispatches"] = dispatch_ledger(state, facts["issue_comments"], issue, policy)
    implementation = None
    for comment in sorted(facts["issue_comments"], key=comment_order):
        value = envelope(comment.get("body"), RECEIPT)
        if (author_matches(comment.get("user"), policy["owner"]) and value
                and value.get("repository") == REPOSITORY and value.get("issue") == issue
                and value.get("active") is True and valid_receipt(issue, policy, value.get("dispatch"))):
            item = value["dispatch"]
            if policy["initial_dispatch"] is None:
                if item["action_type"] == "implementation_task" and item["purpose_id"] == policy["purpose"]:
                    current = next(r for r in state["dispatches"]
                                   if r["dedup_key"] == item["dedup_key"] and r["run_id"] == item["run_id"])
                    if item["attempt"] > 1:
                        parent = next((r for r in state["dispatches"]
                                       if r["run_id"] == item.get("retry_of")
                                       and r["dedup_key"] == item["dedup_key"]
                                       and r["attempt"] == item["attempt"] - 1), None)
                        if parent is None or parent["state"] not in {"FAILED", "CANCELLED"}:
                            raise ValueError("Initial implementation retry lacks its failed/cancelled predecessor")
                    if (implementation and implementation["run_id"] != current["run_id"]
                            and implementation["state"] in {"FAILED", "CANCELLED"}
                            and (current.get("retry_of") != implementation["run_id"]
                                 or current["dedup_key"] != implementation["dedup_key"]
                                 or current["attempt"] != implementation["attempt"] + 1)):
                        raise ValueError("Failed initial implementation requires an explicit same-key retry")
                    implementation = current
            state.update(active_action=item["action_type"], purpose_id=item["purpose_id"],
                         dedup_key=item["dedup_key"], active_run_id=item["run_id"])
    active = next((r for r in state["dispatches"] if r["run_id"] == state["active_run_id"] and r["dedup_key"] == state["dedup_key"]), None)
    if not active:
        if not undispatched(state, policy):
            raise ValueError("Active dispatch identity disappeared")
        # No run identity is manufactured, and a linked PR cannot bypass dispatch.
        unexpected_pr = facts.get("pr") is not None
        state["blockers"] = ["Authenticated initial dispatch receipt is required"] if unexpected_pr else []
        state["current_state"] = "SAFE_STOPPED" if unexpected_pr else "AUTOMATION_ARMED"
        state["merge_gate"] = result("BLOCKED" if unexpected_pr else "PENDING",
                                     "No authenticated active dispatch; implementation not started")
        state["completion_gate"] = result("PENDING", "Implementation not started; not merged")
        if state["current_state"] != old_state:
            state["last_transition"] = f'{old_state} -> {state["current_state"]}'
        return state
    state["dispatch_state"] = active["state"]
    if policy["initial_dispatch"] is None and implementation is None:
        raise ValueError("Authenticated initial implementation receipt is missing")
    state["blockers"] = []
    groups = {}
    for item in state["dispatches"]:
        if item["state"] in {"RUNNING", "SUCCEEDED"}:
            groups.setdefault(item["dedup_key"], []).append(item)
    if any(len(v) > 1 for v in groups.values()):
        state["blockers"].append("DUPLICATE_DISPATCH_DETECTED: owner must select the canonical run")
    if any(r["state"] in {"UNKNOWN", "REQUESTED", "DISPATCHING"} for r in state["dispatches"]):
        state["blockers"].append("DISPATCH_STATE_UNKNOWN: external owner confirmation required")
    if policy["initial_dispatch"] is None:
        if implementation["state"] not in {"RUNNING", "SUCCEEDED"}:
            state["blockers"].append("Initial implementation is not running or successful")
        if active["state"] in {"FAILED", "CANCELLED"}:
            state["blockers"].append("Active dispatch failed or was cancelled")
    pull = facts.get("pr")
    if pull is None:
        if policy["initial_dispatch"] is None:
            state["current_state"] = "IMPLEMENTING" if active["state"] in {"RUNNING", "SUCCEEDED"} else "SAFE_STOPPED"
            state["current_actor"] = policy["dispatch_owners"][active["action_type"]]
            if state["current_state"] != old_state:
                state["last_transition"] = f'{old_state} -> {state["current_state"]}'
        state["merge_gate"] = combine([result("PENDING", "No unique linked PR"),
                                      result("BLOCKED" if state["blockers"] else "PASS", "Ownership/dedup blockers")])
        state["completion_gate"] = result("PENDING", "Not merged")
        if state["blockers"]:
            state["current_state"] = "SAFE_STOPPED"
        if state["pr"] is not None:
            state["current_state"] = "SAFE_STOPPED"
            state["merge_gate"] = result("ERROR", "Previously bound PR is missing")
            state["completion_gate"] = copy.deepcopy(state["merge_gate"])
        return state
    base = pull.get("base") or {}
    head = (pull.get("head") or {}).get("sha")
    if (not sha(head) or (base.get("repo") or {}).get("full_name") != REPOSITORY
            or base.get("ref") != "main" or type(pull.get("number")) is not int
            or (state["pr"] is not None and state["pr"] != pull["number"])):
        raise ValueError("PR/state identity conflict")
    if (pull.get("merged") and state["active_action"] == "fix_task"
            and any(r["dedup_key"] == state["dedup_key"] and r["target_sha"] == pull.get("merge_commit_sha")
                    for r in state["dispatches"])):
        state["blockers"].append("POST_MERGE_FIX_REQUIRES_PR_HANDOFF")
    state["pr"], state["head_sha"] = pull["number"], head
    work, report = work_review(facts["pr_comments"], issue, pull["number"], head, policy, facts.get("reviews"))
    state["work_review"] = work
    state["follow_up"] = (report or {}).get("follow_up", [])
    state["follow_up_recorded"] = (report or {}).get("follow_up_recorded") is True
    state["blockers"] += (report or {}).get("blockers", [])
    # GitHub reviews are additional vetoes, never a replacement for independent Work.
    latest = {}
    for review in sorted(facts["reviews"], key=lambda r: r["id"]):
        if review.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[review["user"]["id"]] = review
    if any(r.get("state") == "CHANGES_REQUESTED" for r in latest.values()):
        state["blockers"].append("Unresolved GitHub changes-requested review")
    ubuntu, windows, public = ci_evidence(facts, head)
    state["ci_ubuntu"], state["ci_windows"], state["public_data"] = ubuntu, windows, public
    state["required_ci"] = combine([ubuntu, windows])
    state["ci_head_sha"] = head if state["required_ci"]["status"] == "PASS" else None
    state["conditions"] = {name: condition(name, policy["requirements"].get(name), report, head, facts)
                           for name in ("windows_validation", "windows_measurement", "artifact_integrity", "measurement_result_pr")}
    body = pull.get("body") or ""
    metadata_ok = (re.search(rf"(?m)^Refs #{issue}\s*$", body) is not None
                   and re.search(rf"Issue #{issue}\b", pull.get("title", "")) is not None
                   and re.search(rf"(?im)^(?:current head|current head sha|実head)\s*:\s*`?{head}`?\s*$", body) is not None
                   and re.search(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#" + str(issue) + r"\b", body) is None)
    # These same-head verification requirements survive human merge. PR-open
    # authorization is a separate lifecycle condition and cannot be reused for
    # a closed, merged PR's Completion Gate.
    verification = [work, state["required_ci"], public]
    preparation_check = None
    if 'preparation_contract' in policy:
        prepared = facts.get('preparation_gate')
        valid = (type(policy['preparation_contract']) is int and policy['preparation_contract'] == 2
                 and isinstance(prepared, dict) and prepared.get('contract') == 2
                 and prepared.get('pr') == pull['number'] and prepared.get('head_sha') == head
                 and prepared.get('phase') in {'PRE_MERGE', 'POST_MERGE', 'FINISHED'}
                 and prepared.get('status') == 'PHASE_EVIDENCE_COMPLETE' and prepared.get('missing') == [])
        preparation_check = result('PASS' if valid else 'BLOCKED',
                                   'Scoped v2 preparation evidence current' if valid else
                                   'Scoped v2 registration/settings/waiting evidence missing: ' +
                                   '; '.join((prepared or {}).get('missing', ['fresh preparation reader required'])))
    checks = [*verification, *([preparation_check] if preparation_check else []), *state["conditions"].values(),
              result("PASS" if metadata_ok else "PENDING", "PR title/Refs/current head must be current; auto-close is prohibited"),
              result("BLOCKED" if state["blockers"] else "PASS", "Active/IN_SCOPE/ownership blockers"),
              result("PASS" if pull.get("state") == "open" and not pull.get("draft") else "BLOCKED", "PR must be open and ready")]
    state["merge_gate"] = combine(checks)
    state["current_actor"] = "Work / GitHub Actions"
    if pull.get("merged") is True:
        if (not sha(pull.get("merge_commit_sha")) or not pull.get("merged_at")
                or not isinstance(pull.get("merged_by"), dict) or pull["merged_by"].get("type") != "User"):
            raise ValueError("Human merge is not confirmed")
        state["merge_sha"] = pull["merge_commit_sha"]
        state["merge_state"] = "MERGED"
        state["local_sync"] = sync_evidence(facts, state["merge_sha"])
        state["local_sync_target_sha"] = state["local_sync"].get("target_sha")
        smoke = result("PENDING", "Post-merge live smoke confirmation is required")
        for comment in facts["issue_comments"]:
            record = envelope(comment.get("body"), SMOKE)
            if (author_matches(comment.get("user"), policy["owner"]) and record
                    and record.get("schema_version") == 1 and record.get("repository") == REPOSITORY
                    and record.get("issue") == issue and record.get("pr") == pull["number"]
                    and record.get("merge_sha") == state["merge_sha"]
                    and record.get("dashboard_comment_id") == facts["dashboard_comment_id"]
                    and record.get("sync_run_id") == state["local_sync"].get("run_id")
                    and record.get("observed_state") == "LOCAL_SYNCED" and record.get("status") == "PASS"):
                smoke = result("PASS", "Owner confirmed same-comment merge/sync live smoke")
        state["conditions"]["live_smoke"] = (result("NOT_REQUIRED", "Explicit trusted policy")
                                                      if policy["requirements"].get("live_smoke") == "NOT_REQUIRED" else smoke)
        preparation_post = []
        if preparation_check:
            prepared = facts.get('preparation_gate') or {}
            preparation_post = [preparation_check,
                result('PASS' if prepared.get('phase') in {'POST_MERGE', 'FINISHED'}
                       and prepared.get('i01_live') == 'OWNER_OBSERVED' else 'PENDING',
                       'Actual owner resume event/start/claim/receipt/ZIP/next operation must be observed')]
        post = [*verification, *preparation_post, state["local_sync"], *state["conditions"].values(),
                result("PASS" if state["follow_up_recorded"] else "PENDING", "FOLLOW_UP must be explicitly recorded"),
                result("BLOCKED" if state["blockers"] else "PASS", "Active/IN_SCOPE/ownership blockers")]
        state["completion_gate"] = combine(post)
        state["current_state"] = ("COMPLETED" if state["completion_gate"]["status"] == "PASS" else
                                  "LOCAL_SYNCED" if state["local_sync"]["status"] == "PASS" else "MERGED_SYNC_PENDING")
        state["merge_gate"] = result("BLOCKED", "PR already merged; no merge authorization")
    else:
        state["merge_state"], state["merge_sha"] = "PENDING", None
        state["local_sync"] = result("PENDING", "Human merge is not confirmed")
        state["local_sync_target_sha"] = None
        state["completion_gate"] = result("PENDING", "Human merge is not confirmed")
        state["current_state"] = "READY_FOR_HUMAN_MERGE" if state["merge_gate"]["status"] == "PASS" else "REVIEWING"
        if state["merge_gate"]["status"] in {"ERROR", "BLOCKED"}:
            state["current_state"] = "FIX_REQUIRED"
    if state["current_state"] != old_state:
        state["last_transition"] = f'{old_state} -> {state["current_state"]}'
    return state


def text_cell(value):
    # No HTML, links, multiline table injection, credential-bearing URLs or paths.
    value = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", " ")


def render(state):
    if __package__:
        from .automation_dashboard_display import render_markdown
    else:
        from automation_dashboard_display import render_markdown

    payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")
    return render_markdown(state, REPOSITORY) + "\n\n" + START + payload + END + "\n"
