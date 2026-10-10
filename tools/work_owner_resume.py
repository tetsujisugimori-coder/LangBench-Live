#!/usr/bin/env python3
"""I-01 Work merge handoff validation; read-only GitHub, no dispatch or Gate writes.

Work supplies observations from its supported event/UI execution. This module
does not claim access to a private Work API or cross-environment exclusion.
"""
from __future__ import annotations
import zipfile

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile

try:
    from tools import startup_preparation as preparation
    from tools.automation_dashboard import REPOSITORY, author_matches, sha, sync_evidence, work_review, initial_state
    from tools.update_automation_dashboard import GitHub, collect, references
except ModuleNotFoundError:
    import startup_preparation as preparation
    from automation_dashboard import REPOSITORY, author_matches, sha, sync_evidence, work_review, initial_state
    from update_automation_dashboard import GitHub, collect, references

PURPOSE = 'work-owner-resume-i01'
REPAIR_SCOPE = (102, 'work-owner-resume-i01-repair')
ACTION = 'owner_resume'
CLAIM_START = '<!-- langbench-owner-resume-claim:v1\n'
CLAIM_END = '\nlangbench-owner-resume-claim:end -->'
FIELDS = {'schema_version', 'repository', 'issue', 'purpose', 'pr', 'reviewed_head_sha',
          'merge_sha', 'target_main_sha', 'owner', 'waiting_record', 'event', 'work',
          'claim', 'receipt', 'next_action', 'recheck'}


def capability_contract():
    try:
        from tools import work_resume_claim
    except ModuleNotFoundError:
        import work_resume_claim
    return work_resume_claim


def positive(value):
    return type(value) is int and value > 0


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    """A reference and time are observations, never independently authenticated Work facts."""
    if not isinstance(value, dict) or not nonempty(value.get('evidence_url')):
        raise ValueError('Missing Work evidence reference')
    if not value['evidence_url'].startswith('https://'):
        raise ValueError('Evidence must use an HTTPS reference')
    preparation.timestamp(value.get('observed_at'))


def instant(value):
    preparation.timestamp(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def save_observation(path, value):
    """Atomic local cache only; its lock cannot exclude another Work environment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(preparation.canonical(value) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def key(value):
    return f'{REPOSITORY}:issue{value["issue"]}:{value["target_main_sha"]}:{ACTION}:{value["purpose"]}'


def supported_scope(value):
    """Preserve the original contract; opt in only Issue102's explicit v2 repair."""
    return (value.get('purpose') == PURPOSE
            or (value.get('schema_version') == 2
                and (value.get('issue'), value.get('purpose')) == REPAIR_SCOPE))


def validate(value):
    if not isinstance(value, dict) or set(value) != (FIELDS | {'authorization'} if value.get('schema_version') == 2 else FIELDS):
        raise ValueError('Unknown/missing handoff fields')
    if (type(value['schema_version']) is not int or value['schema_version'] not in (1, 2)
            or value['repository'] != REPOSITORY or not supported_scope(value)
            or not positive(value['issue']) or not positive(value['pr'])
            or any(not sha(value[k]) for k in ('reviewed_head_sha', 'merge_sha', 'target_main_sha'))
            or value['merge_sha'] != value['target_main_sha']):
        raise ValueError('Invalid handoff scope/SHA')
    preparation.identity(value['owner'])
    waiting = value['waiting_record']
    if (not isinstance(waiting, dict) or set(waiting) != {'comment_id', 'body_sha256'}
            or not positive(waiting['comment_id'])
            or not isinstance(waiting['body_sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', waiting['body_sha256'])):
        raise ValueError('Invalid waiting-record binding')
    event = value['event']
    if (not isinstance(event, dict) or set(event) != {'delivery_id', 'repository', 'pr', 'action',
                                                   'head_sha', 'merge_sha', 'evidence_url', 'observed_at'}
            or not nonempty(event['delivery_id']) or event['repository'] != REPOSITORY
            or type(event['pr']) is not int or event['pr'] != value['pr'] or event['action'] != 'closed'
            or event['head_sha'] != value['reviewed_head_sha'] or event['merge_sha'] != value['merge_sha']):
        raise ValueError('Event/handoff binding mismatch')
    evidence(event)
    work = value['work']
    if value['schema_version'] == 2:
        capability = capability_contract()
        capability.validate_identity(value)
    elif (not isinstance(work, dict) or set(work) != {'run_id', 'automation_id', 'started_at', 'evidence_url', 'observed_at'}
            or not nonempty(work['run_id']) or not isinstance(work['automation_id'], str)
            or not re.fullmatch('[0-9a-f]{32}', work['automation_id'])):
        raise ValueError('Missing real Work start identity')
    evidence(work)
    preparation.timestamp(work['started_at'])
    if instant(work['observed_at']) < instant(work['started_at']):
        raise ValueError('Work observation predates start')
    if value['schema_version'] == 2:
        capability.validate_records(value)
        return value
    for field in ('claim', 'receipt', 'next_action', 'recheck'):
        record = value[field]
        if record is not None:
            evidence(record)
    claim = value['claim']
    if claim is not None and (set(claim) != {'dedup_key', 'run_id', 'owner', 'status', 'evidence_url', 'observed_at'}
                             or claim['dedup_key'] != key(value) or claim['owner'] != 'Work(root)'
                             or claim['run_id'] != work['run_id'] or claim['status'] not in {'RUNNING', 'UNKNOWN', 'FAILED', 'CANCELLED'}):
        raise ValueError('Claim identity/status mismatch')
    receipt = value['receipt']
    if receipt is not None and (set(receipt) != {'run_id', 'waiting_comment_id', 'waiting_body_sha256', 'evidence_url', 'observed_at'}
                               or receipt['run_id'] != work['run_id']
                               or receipt['waiting_comment_id'] != waiting['comment_id']
                               or receipt['waiting_body_sha256'] != waiting['body_sha256']):
        raise ValueError('Receipt does not bind this Work/waiting record')
    action = value['next_action']
    if action is not None and (set(action) != {'run_id', 'dedup_key', 'kind', 'status', 'authorization_ref', 'evidence_url', 'observed_at'}
                              or action['run_id'] != work['run_id'] or action['dedup_key'] != key(value)
                              or action['kind'] not in {'live_smoke', 'safe_stop'}
                              or action['status'] not in {'EXECUTED', 'UNKNOWN', 'FAILED', 'CANCELLED', 'NO_OP'}
                              or not nonempty(action['authorization_ref'])):
        raise ValueError('Next action evidence invalid')
    recheck = value['recheck']
    if recheck is not None and (set(recheck) != {'id', 'enabled', 'dedup_key', 'run_id', 'stop_condition', 'evidence_url', 'observed_at'}
                               or not nonempty(recheck['id']) or recheck['enabled'] is not True
                               or recheck['dedup_key'] != key(value) or recheck['run_id'] != work['run_id']
                               or recheck['stop_condition'] != 'sync terminal or target changed'):
        raise ValueError('Recheck is not a registered bounded waiting route')
    return value


def waiting_digest(body):
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


class ObservationGitHub(GitHub):
    """Keep ZIP verification references alongside the existing safety report."""
    def __init__(self, token=None, sync_artifact_zip=None):
        super().__init__(token, sync_artifact_zip)
        self.artifacts = {}
        self.zip_digest = None

    def request(self, path, method='GET', data=None, raw=False):
        if method != 'GET':
            raise ValueError('Owner resume adapter is strictly read-only')
        result = super().request(path, method, data, raw)
        if raw:
            self.zip_digest = 'sha256:' + hashlib.sha256(result).hexdigest()
        return result

    def sync_report(self, run):
        self.zip_digest = None
        report = super().sync_report(run)
        if report is not None:
            if self.sync_artifact_zip is not None:
                self.zip_digest = self.sync_artifacts[str(run['id'])]['digest']
            expected = f'local-main-sync-{run["id"]}-attempt{run["run_attempt"]}'
            artifacts = self.pages(f'/actions/runs/{run["id"]}/artifacts', 'artifacts')
            matches = [a for a in artifacts if a.get('name') == expected and a.get('expired') is False]
            if (len(matches) != 1 or matches[0].get('digest') != self.zip_digest
                    or matches[0].get('id') != self.sync_artifacts[str(run['id'])]['artifact_id']):
                raise ValueError('Artifact identity changed after ZIP verification')
            item = matches[0]
            self.artifacts[str(run['id'])] = {'artifact_id': item['id'], 'name': expected,
                                             'digest': self.zip_digest,
                                             'zip_verified': True,
                                             'evidence_url': f'https://github.com/{REPOSITORY}/actions/runs/{run["id"]}/artifacts/{item["id"]}'}
        return report


def read_facts(api, value, include_reservation=True):
    """Reuse the official collection and digest-checked sync-report adapter.

    Double collection detects observed changes; it is not a transactional claim.
    No mutation, POST, arbitrary Work API, workflow dispatch, or rerun.
    """
    main = api.get('/branches/main')['commit']['sha']
    if not sha(main):
        raise ValueError('Invalid current main SHA')
    config = api.get(f'/contents/.github/automation-dashboard.json?ref={main}')
    decoded = preparation.loads(base64.b64decode(config['content']).decode())
    try:
        from tools.automation_dashboard import validate_policy_config
    except ModuleNotFoundError:
        from automation_dashboard import validate_policy_config
    validate_policy_config(decoded)
    policy = decoded['issues'][str(value['issue'])]
    prior = initial_state(value['issue'], policy)
    prior['pr'] = value['pr']
    _, facts = collect(api, value['issue'], policy, prior, include_preparation=False)
    facts.update(main_sha=main, policy=policy, issue=api.get(f'/issues/{value["issue"]}'))
    if facts.get('dashboard_comment_id') is not None:
        dashboards=[item for item in api.pages(f'/issues/{value["issue"]}/comments') if item.get('id')==facts['dashboard_comment_id']]
        if len(dashboards)!=1:raise ValueError('Current Dashboard identity unavailable')
        # Rendered Dashboard is read separately only for the actual smoke.
        facts['smoke_dashboard']=dashboards[0]
    facts['sync_artifacts'] = copy.deepcopy(getattr(api, 'artifacts', getattr(api, 'sync_artifacts', {})))
    if api.get('/branches/main')['commit']['sha'] != main:
        raise ValueError('main advanced during collection')
    if value['schema_version'] == 2:
        try:
            from tools.preparation_github import select_preparation
        except ModuleNotFoundError:
            from preparation_github import select_preparation
        _, record, _ = select_preparation(facts['issue_comments'], value['issue'], policy)
        waiting = (record['owner_facts'] or {}).get('waiting_record')
        if (record['input']['owner_resume_id'] != value['work']['automation_id']
                or record['input']['head_sha'] != value['reviewed_head_sha'] or waiting is None
                or waiting['comment_id'] != value['waiting_record']['comment_id']
                or waiting['body_sha256'] != value['waiting_record']['body_sha256']):
            raise ValueError('Current authenticated preparation/resume/waiting binding differs')
        facts['resume_authorization'] = dict(kind=waiting['allowed_action'], authorization_ref=waiting['authorization_ref'], effect='read_only')
    if value['schema_version'] == 2 and value['work']['identity']['route'] == 'managed':
        try:
            from tools.i01_management import authenticate_managed_handoff
        except ModuleNotFoundError:
            from i01_management import authenticate_managed_handoff
        authenticate_managed_handoff(value, facts['issue_comments'], policy)
        facts['managed_actor_verified'] = True
    if value['schema_version'] == 2 and include_reservation and value['work']['identity']['route'] in {'automatic', 'managed'}:
        capability = capability_contract()
        facts['resume_reservation'] = capability.read_reservation(api, value)
    return facts


def execution_id(value):
    # Names remain distinct: capability ID is never inserted into run_id.
    return value['work']['identity']['public_id'] if value['schema_version'] == 2 else value['work']['run_id']


def read_only_smoke(value, facts, previous=None):
    """Receive actual waiting bytes and read the existing bound Dashboard.

    No external write. The caller must have verified local capability possession
    for the automatic route. This is repeatable even after an interrupted read.
    """
    validate(value)
    if value['schema_version'] != 2 or value['authorization']['kind'] != 'live_smoke':
        raise ValueError('Read-only smoke requires explicit v2 live_smoke authorization')
    updated=copy.deepcopy(value)
    now=datetime.now(timezone.utc).isoformat()
    updated['receipt']=dict(execution_id=execution_id(value),
        waiting_comment_id=value['waiting_record']['comment_id'],
        waiting_body_sha256=value['waiting_record']['body_sha256'],
        evidence_url=f'https://github.com/{REPOSITORY}/issues/{value["issue"]}#issuecomment-{value["waiting_record"]["comment_id"]}',
        observed_at=now)
    updated['next_action']=None
    checked=observe(updated,facts,previous)
    # observe has already authenticated scope, authorization, claim, waiting,
    # history and ZIP before reaching precisely this missing-action boundary.
    if checked['reason'] != 'Actual next operation is missing or non-successful; no I-01 live success':
        raise ValueError('Read-only smoke preflight stopped: '+checked['reason'])
    try:
        from tools.automation_dashboard import parse_state, BOT
    except ModuleNotFoundError:
        from automation_dashboard import parse_state, BOT
    matches=[c for c in facts['issue_comments'] if c.get('id')==facts.get('dashboard_comment_id')]
    if facts.get('smoke_dashboard') is not None:matches=[facts['smoke_dashboard']]
    if len(matches)!=1 or not author_matches(matches[0].get('user'),BOT):
        raise ValueError('Sole-writer Dashboard unavailable')
    dashboard=parse_state(matches[0]['body'],value['issue'],facts['policy'])
    if (not dashboard or dashboard['issue']!=value['issue'] or dashboard['pr']!=value['pr']
            or dashboard['head_sha']!=value['reviewed_head_sha'] or dashboard['merge_sha']!=value['merge_sha']
            or dashboard['current_state']!='LOCAL_SYNCED' or dashboard['local_sync']['status']!='PASS'
            or dashboard['local_sync']['target_sha']!=value['merge_sha']):
        raise ValueError('Current Dashboard/exact-sync read-only smoke mismatch')
    updated['next_action']=dict(execution_id=execution_id(value),dedup_key=key(value),
        kind='live_smoke',status='EXECUTED',effect='read_only',
        authorization_ref=value['authorization']['authorization_ref'],
        evidence_url=f'https://github.com/{REPOSITORY}/issues/{value["issue"]}#issuecomment-{matches[0]["id"]}',
        observed_at=datetime.now(timezone.utc).isoformat())
    return validate(updated)


def observe(value, facts, previous=None):
    """Pure result; synthetic facts must never be reported as live verification."""
    validate(value)
    if previous is not None:
        if (not isinstance(previous, dict) or previous.get('kind') != 'work_owner_resume_observation'
                or previous.get('schema_version') != value['schema_version'] or previous.get('dedup_key') != key(value)):
            raise ValueError('Previous observation scope/schema mismatch')
    history = copy.deepcopy(previous.get('evidence_history', {}) if previous else {})
    conflicts = copy.deepcopy(previous.get('evidence_conflicts', {}) if previous else {})
    if not isinstance(history, dict) or not isinstance(conflicts, dict):
        raise ValueError('Invalid saved evidence history')
    for record in history.values():
        evidence(record)
    for observed_at in conflicts.values():
        instant(observed_at)
    out = {'schema_version': value['schema_version'], 'kind': 'work_owner_resume_observation', 'dedup_key': key(value),
           'stage': '実装済み', 'status': 'STOPPED', 'reason': '', 'next_owner': 'Work(root)',
           'next_action': 'Inspect current facts; no dispatch', 'event': copy.deepcopy(value['event']),
           'work': copy.deepcopy(value['work']), 'receipt': copy.deepcopy(value['receipt']),
           'action': copy.deepcopy(value['next_action']), 'sync': None, 'recheck': copy.deepcopy(value['recheck']),
           'matched': False, 'gate_certified': False, 'deadline_guaranteed': False,
           'waiting_record': copy.deepcopy(value['waiting_record']), 'owner': copy.deepcopy(value['owner']),
           'claimed_run_id': previous.get('claimed_run_id', previous['work']['run_id']) if previous else value['work']['run_id'],
           'claimed_started_at': previous.get('claimed_started_at', previous['work']['started_at']) if previous else value['work']['started_at'],
           'evidence_history': history, 'evidence_conflicts': conflicts,
           'input_digest': preparation.digest(value), 'facts_digest': preparation.digest({k:v for k,v in facts.items() if k!='smoke_dashboard'})}

    if value['schema_version'] == 2:
        out.update(claimed_execution_id=previous.get('claimed_execution_id') if previous else execution_id(value),
                   identity_assurance=('GitHub actor; not authenticated Work run' if value['work']['identity']['route']=='managed' else 'capability possession; not authenticated Work run'),
                   resume_route=value['work']['identity']['route'])

    def stop(reason):
        out['reason'] = reason
        return out

    observations = {field: value['next_action'] if field == 'action' else value[field]
                    for field in ('event', 'work', 'claim', 'receipt', 'action', 'recheck')}
    out['attempted_evidence'] = copy.deepcopy(observations)

    def inspect_history(negative_only=False):
        # Classify EVERY field before returning a rejection. Independently newer
        # negative observations must survive a stale/conflicting sibling field.
        errors, candidates = [], {}
        for field, current in observations.items():
            if current is None:
                continue
            negative = current.get('status') in {'FAILED', 'CANCELLED', 'UNKNOWN'}
            if negative_only and not negative:
                continue
            prior = history.get(field)
            observed_at = instant(current['observed_at'])
            if field != 'event' and observed_at < instant(value['work']['started_at']):
                errors.append('Evidence predates this Work start')
            elif field in conflicts and observed_at <= instant(conflicts[field]):
                errors.append('Conflicting evidence requires a newer authenticated observation')
            elif prior and observed_at < instant(prior['observed_at']):
                errors.append('Late observation must not roll back newer Work evidence')
            elif prior and observed_at == instant(prior['observed_at']) and current != prior:
                conflicts[field] = current['observed_at']
                errors.append('Different Work evidence at the same observation time')
            else:
                candidates[field] = copy.deepcopy(current)
                if negative:
                    history[field] = copy.deepcopy(current)
                    conflicts.pop(field, None)
        return errors, candidates

    # Work observations are explicit owner attestations. For the previously
    # bound owner/run/scope only, retain newer negatives even when fresh GitHub
    # facts cannot be collected. This can prohibit success, never authorize it.
    bound_event = history.get('event', {})
    if (previous and previous.get('owner') == value['owner']
            and previous.get('waiting_record') == value['waiting_record']
            and (out.get('claimed_execution_id') == execution_id(value) if value['schema_version'] == 2
                 else out['claimed_run_id'] == value['work']['run_id'])
            and out['claimed_started_at'] == value['work']['started_at']
            and all(bound_event.get(k) == value['event'][k]
                    for k in ('repository', 'pr', 'head_sha', 'merge_sha'))):
        inspect_history(negative_only=True)

    if facts.get('fetch_error'):
        return stop('GitHub retrieval failed; cached success is not current evidence')
    try:
        pull, policy, issue = facts['pr'], facts['policy'], facts['issue']
        if (policy['purpose'] != value['purpose'] or policy['owner'] != value['owner']
                or policy['dispatch_owners']['implementation_task'] != 'Work(root)'
                or policy['dispatch_owners']['fix_task'] != 'Work(root)'
                or policy['dispatch_owners']['local_main_sync'] != '.github/workflows/pull-local-main.yml'
                or issue['number'] != value['issue'] or 'pull_request' in issue
                or not author_matches(issue.get('user'), value['owner'])
                or re.search(r'(?m)^purpose:\s*`?' + re.escape(value['purpose']) + r'`?\s*$', issue.get('body', '')) is None
                or pull['number'] != value['pr'] or pull['base']['repo']['full_name'] != REPOSITORY
                or pull['base']['ref'] != 'main' or pull['merged'] is not True
                or not author_matches(pull['merged_by'], value['owner'])
                or pull['head']['sha'] != value['reviewed_head_sha']
                or pull['merge_commit_sha'] != value['merge_sha'] or facts['main_sha'] != value['target_main_sha']
                or not references(pull.get('body'), value['issue'])):
            return stop('Current repository/Issue/purpose/owner/PR/merge/main binding mismatch')
        if value['schema_version'] == 2 and facts.get('resume_authorization') != value['authorization']:
            return stop('Fresh owner authorization does not bind this reserved operation')
        if value['schema_version'] == 2 and policy.get('resume_protocol') != 2:
            return stop('Trusted main policy has not enabled the explicit capability protocol')
        if value['schema_version'] == 1 and policy.get('resume_protocol') == 2:
            return stop('Legacy comment claim cannot authorize this protocol; migrate without relabeling run identity')
        merged_at = instant(pull['merged_at'])
        if instant(value['work']['started_at']) < merged_at:
            return stop('Work started before the human merge')
        if instant(value['event']['observed_at']) < merged_at:
            return stop('Event observation predates merge')
        waiting = [c for c in facts['issue_comments'] if c['id'] == value['waiting_record']['comment_id']]
        if (len(waiting) != 1 or not author_matches(waiting[0].get('user'), value['owner'])
                or waiting_digest(waiting[0]['body']) != value['waiting_record']['body_sha256']):
            return stop('Prior owner waiting record is missing, changed, or untrusted')
    except (KeyError, TypeError, ValueError):
        return stop('Required fresh GitHub fields are missing or invalid')
    if value['schema_version'] == 2 and value['work']['identity']['route'] == 'managed' and facts.get('managed_actor_verified') is not True:
        return stop('Managed GitHub actor request has not been freshly authenticated')
    out.update(matched=True, stage='実装済み')
    try:
        review, _ = work_review(facts['pr_comments'], value['issue'], value['pr'], value['reviewed_head_sha'], policy, facts.get('reviews'))
        if review['status'] != 'PASS' or value['work']['automation_id'] == policy['work_automation_id']:
            return stop('Independent reviewed HEAD is unconfirmed or reviewer is acting as resume owner')
    except (KeyError, TypeError, ValueError):
        return stop('Independent review facts are missing or invalid')
    if (out.get('claimed_execution_id') if value['schema_version'] == 2 else out['claimed_run_id']) != execution_id(value):
        return stop('Different Work run already observed for this dedup key; reconcile shared ownership')
    if previous:
        if out['claimed_started_at'] != value['work']['started_at']:
            return stop('Work start identity changed')
    def reject_evidence(reason):
        # Retain the accepted current-view fields too (Work(root)'s minimal R1
        # repair), while keeping the rejected attempt separately inspectable.
        for field, record in history.items():
            if field in out:
                out[field] = copy.deepcopy(record)
        return stop(reason)

    errors, candidates = inspect_history()
    claim = value['claim']
    manual = value['schema_version'] == 2 and value['work']['identity']['route'] == 'manual'
    if manual:
        capability = capability_contract()
        problem = capability.check_manual(value, facts['issue_comments'])
        if problem: return stop(problem)
    elif claim is None:
        return stop('Single-owner claim missing; no next operation')
    claim_time = value['work']['started_at'] if manual else claim['observed_at']
    if instant(claim_time) < instant(value['work']['started_at']):
        return stop('Shared claim predates this Work start')
    if manual:
        pass # Human authorization permits read-only observations, not takeover.
    elif value['schema_version'] == 2:
        capability = capability_contract()
        problem = capability.check_reservation(value, facts.get('resume_reservation'))
        if problem: return stop(problem)
    else:
        # Re-read all shared claims, not a local file lock. Comment POST has no CAS:
        # concurrent claims are detected and both stop, rather than select a winner.
        claims = []
        try:
            for comment in facts['issue_comments']:
                body = comment.get('body', '')
                if CLAIM_START not in body and CLAIM_END not in body:
                    continue
                if (body.count(CLAIM_START) != 1 or body.count(CLAIM_END) != 1
                        or not author_matches(comment.get('user'), value['owner'])):
                    return stop('Ambiguous or untrusted shared owner claim')
                raw = body.split(CLAIM_START, 1)[1].split(CLAIM_END, 1)[0]
                record = preparation.loads(raw)
                if record.get('dedup_key') == key(value):
                    claims.append(record)
            if len(claims) != 1 or claims[0] != claim:
                return stop('Missing/conflicting shared claim; no cross-environment exclusion established')
        except (KeyError, TypeError, ValueError):
            return stop('Shared claim could not be authenticated')
    # Positive observations require fresh GitHub scope and shared ownership.
    # This adapter never executes external writes. Legacy comment claims are
    # observational only and cannot authorize any mutation.
    # Negative candidates have already been retained regardless of siblings.
    history.update(candidates)
    for field in candidates:
        conflicts.pop(field, None)
    if errors:
        return reject_evidence('; '.join(dict.fromkeys(errors)))
    if value['receipt'] is None:
        return stop('Work receipt of the exact prior waiting record is missing')
    receipt_time = instant(value['receipt']['observed_at'])
    action = value['next_action']
    if (receipt_time < instant(claim_time)
            or (action is not None and instant(action['observed_at']) < receipt_time)):
        return stop('Receipt/next operation predates the owner claim or receipt')
    # The history contains bound observations, including newer negative results.
    # A rejected attempt stays in the current view but never lowers this history.
    # Updating history is not an execution/success certification.
    if not manual and claim['status'] != 'RUNNING':
        return stop('Single-owner claim non-running; no next operation')
    try:
        sync = sync_evidence(facts, value['merge_sha'])
    except (KeyError, TypeError, ValueError):
        return stop('Official sync facts unavailable')
    out['sync'] = sync
    if sync['status'] == 'PENDING':
        out.update(status='WAITING', reason='Formal sync pending; completion is unverified',
                   next_action='Read existing sync; register a pending-only recheck if this execution cannot continue')
        if value['recheck'] is not None:
            out['next_action'] = 'Wait for registered recheck ' + value['recheck']['id']
        return out
    if sync['status'] != 'PASS':
        return stop('Official sync failed/unknown or safety artifact mismatch: ' + sync['reason'])
    artifact = facts.get('sync_artifacts', {}).get(str(sync['run_id']))
    if (not isinstance(artifact, dict) or artifact.get('zip_verified') is not True
            or not positive(artifact.get('artifact_id')) or not nonempty(artifact.get('evidence_url'))
            or not isinstance(artifact.get('digest'), str)
            or not re.fullmatch('sha256:[0-9a-f]{64}', artifact['digest'])
            or artifact.get('name') != f'local-main-sync-{sync["run_id"]}-attempt{sync["run_attempt"]}'):
        return stop('Verified ZIP identity/digest observation missing')
    out['sync']['artifact'] = copy.deepcopy(artifact)
    out['sync']['report'] = copy.deepcopy(facts['sync_reports'][str(sync['run_id'])])
    if action is None or action['status'] != 'EXECUTED':
        return stop('Actual next operation is missing or non-successful; no I-01 live success')
    # Action and receipt observations must belong to this execution and postdate merge/sync.
    action_time = instant(action['observed_at'])
    run = next((r for r in facts['sync_runs'] if r['id'] == sync['run_id']), None)
    if (receipt_time < instant(claim_time) or action_time < receipt_time
            or run is None or not run.get('updated_at')
            or action_time < instant(run['updated_at'])):
        return stop('Receipt/next operation predates Work start or formal sync completion')
    if value['schema_version'] == 2 and value['work']['identity']['route'] == 'manual':
        out.update(status='MANUAL_OBSERVED', reason='Human-authorized read-only handling; automatic cycle unverified',
                   next_action='Retain manual handoff; reconcile reserved owner before any external write')
        return out
    out.update(stage='実動確認済み', status='OBSERVED',
               reason='Bound Work start, receipt, exact official sync, and executed next operation observed',
               next_action='Work(root) verifies remaining Completion conditions; this observation grants no Gate PASS')
    return out


def main():
    if getattr(sys.stdout, 'reconfigure', None):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--sync-artifact-zip', type=Path, help='Actual official ZIP download; current API identity/digest still required')
    parser.add_argument('--capability-file', type=Path, help='Private local possession proof for v2 automatic route; never published')
    parser.add_argument('--read-only-smoke', action='store_true', help='Receive waiting bytes and read existing exact-sync Dashboard; no external write')
    parser.add_argument('--updated-handoff', type=Path, help='Save actual receipt/read-only operation for owner-input update')
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--github-read', action='store_true')
    sources.add_argument('--fixture-facts', type=Path, help='Synthetic testing only; cannot certify live results')
    args = parser.parse_args()
    if args.sync_artifact_zip is not None and not args.github_read:
        parser.error('--sync-artifact-zip requires --github-read; it is not fixture evidence')
    if args.read_only_smoke and (not args.github_read or args.updated_handoff is None):
        parser.error('--read-only-smoke requires --github-read and --updated-handoff')
    try:
        value = validate(preparation.loads(args.handoff.read_text(encoding='utf-8')))
        if value['schema_version'] == 2 and value['work']['identity']['route'] == 'automatic':
            if args.capability_file is None:
                raise ValueError('Automatic capability route requires private possession proof')
            capability_contract().verify_possession(value,args.capability_file.read_text(encoding='utf-8').strip())
    except (OSError,KeyError,TypeError,ValueError) as error:
        stopped=dict(status='STOPPED',stage='handoff validation / capability possession',
            reason=str(error) if isinstance(error,ValueError) else type(error).__name__,
            next_owner='Work(root)',next_action='Obtain missing current identity/binding or human read-only authorization',
            retained=['handoff file','prior state unchanged','private capability file if present'])
        # A validation failure must not erase a valid older evidence history.
        save_observation(args.state.with_suffix('.stop.json'),stopped)
        print(preparation.canonical(stopped))
        return 1
    with preparation.state_lock(args.state):
        old = preparation.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else None
        try:
            if args.github_read:
                api = ObservationGitHub(os.environ.get('GH_TOKEN'), args.sync_artifact_zip)
                facts = read_facts(api, value)
                if preparation.digest(facts) != preparation.digest(read_facts(api, value)):
                    raise ValueError('External facts changed during observation')
            else:
                facts = preparation.loads(args.fixture_facts.read_text(encoding='utf-8'))
            if args.read_only_smoke:
                value=read_only_smoke(value,facts,old)
                save_observation(args.updated_handoff,value)
            out = observe(value, facts, old)
        except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as error:
            # Preserve history and invalidate cached success; never retry a mutation.
            out = observe(value, {'fetch_error': True}, old)
            out['reason'] = 'Current fact collection failed: ' + type(error).__name__
        out['source'] = 'github-read + explicit Work observations' if args.github_read else 'synthetic fixture'
        if not args.github_read:
            out['stage'] = '実装済み'
            if out['status'] == 'OBSERVED':
                out['status'] = 'FIXTURE_ONLY'
            elif out['status'] == 'MANUAL_OBSERVED':
                out['status'] = 'MANUAL_FIXTURE_ONLY'
        if old == out:
            print('NO_OP (same observation; no dispatch or success promotion)')
        else:
            save_observation(args.state, out)
            print(preparation.canonical(out))
        return 0 if out['status'] in {'OBSERVED', 'FIXTURE_ONLY', 'MANUAL_OBSERVED', 'MANUAL_FIXTURE_ONLY', 'WAITING'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
