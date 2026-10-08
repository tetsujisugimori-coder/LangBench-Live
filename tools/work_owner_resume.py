#!/usr/bin/env python3
"""I-01 Work merge handoff validation; read-only GitHub, no dispatch or Gate writes.

Work supplies observations from its supported event/UI execution. This module
does not claim access to a private Work API or cross-environment exclusion.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime
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
ACTION = 'owner_resume'
CLAIM_START = '<!-- langbench-owner-resume-claim:v1\n'
CLAIM_END = '\nlangbench-owner-resume-claim:end -->'
FIELDS = {'schema_version', 'repository', 'issue', 'purpose', 'pr', 'reviewed_head_sha',
          'merge_sha', 'target_main_sha', 'owner', 'waiting_record', 'event', 'work',
          'claim', 'receipt', 'next_action', 'recheck'}


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
    return f'{REPOSITORY}:issue{value["issue"]}:{value["target_main_sha"]}:{ACTION}:{PURPOSE}'


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Unknown/missing handoff fields')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['repository'] != REPOSITORY or value['purpose'] != PURPOSE
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
    if (not isinstance(work, dict) or set(work) != {'run_id', 'automation_id', 'started_at', 'evidence_url', 'observed_at'}
            or not nonempty(work['run_id']) or not isinstance(work['automation_id'], str)
            or not re.fullmatch('[0-9a-f]{32}', work['automation_id'])):
        raise ValueError('Missing real Work start identity')
    evidence(work)
    preparation.timestamp(work['started_at'])
    if instant(work['observed_at']) < instant(work['started_at']):
        raise ValueError('Work observation predates start')
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
    def __init__(self, token):
        super().__init__(token)
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
            expected = f'local-main-sync-{run["id"]}-attempt{run["run_attempt"]}'
            artifacts = self.pages(f'/actions/runs/{run["id"]}/artifacts', 'artifacts')
            matches = [a for a in artifacts if a.get('name') == expected and a.get('expired') is False]
            if len(matches) != 1 or matches[0].get('digest') != self.zip_digest:
                raise ValueError('Artifact identity changed after ZIP verification')
            item = matches[0]
            self.artifacts[str(run['id'])] = {'artifact_id': item['id'], 'name': expected,
                                             'digest': self.zip_digest,
                                             'zip_verified': True,
                                             'evidence_url': f'https://github.com/{REPOSITORY}/actions/runs/{run["id"]}/artifacts/{item["id"]}'}
        return report


def read_facts(api, value):
    """Reuse the official collection and digest-checked sync-report adapter.

    Double collection detects observed changes; it is not a transactional claim.
    No mutation, POST, arbitrary Work API, workflow dispatch, or rerun.
    """
    main = api.get('/branches/main')['commit']['sha']
    if not sha(main):
        raise ValueError('Invalid current main SHA')
    config = api.get(f'/contents/.github/automation-dashboard.json?ref={main}')
    policy = preparation.loads(base64.b64decode(config['content']).decode())['issues'][str(value['issue'])]
    prior = initial_state(value['issue'], policy)
    prior['pr'] = value['pr']
    _, facts = collect(api, value['issue'], policy, prior)
    facts.update(main_sha=main, policy=policy, issue=api.get(f'/issues/{value["issue"]}'))
    facts['sync_artifacts'] = copy.deepcopy(getattr(api, 'artifacts', {}))
    if api.get('/branches/main')['commit']['sha'] != main:
        raise ValueError('main advanced during collection')
    return facts


def observe(value, facts, previous=None):
    """Pure result; synthetic facts must never be reported as live verification."""
    validate(value)
    if previous is not None:
        if (not isinstance(previous, dict) or previous.get('kind') != 'work_owner_resume_observation'
                or previous.get('schema_version') != 1 or previous.get('dedup_key') != key(value)):
            raise ValueError('Previous observation scope/schema mismatch')
    history = copy.deepcopy(previous.get('evidence_history', {}) if previous else {})
    conflicts = copy.deepcopy(previous.get('evidence_conflicts', {}) if previous else {})
    if not isinstance(history, dict) or not isinstance(conflicts, dict):
        raise ValueError('Invalid saved evidence history')
    for record in history.values():
        evidence(record)
    for observed_at in conflicts.values():
        instant(observed_at)
    out = {'schema_version': 1, 'kind': 'work_owner_resume_observation', 'dedup_key': key(value),
           'stage': '実装済み', 'status': 'STOPPED', 'reason': '', 'next_owner': 'Work(root)',
           'next_action': 'Inspect current facts; no dispatch', 'event': copy.deepcopy(value['event']),
           'work': copy.deepcopy(value['work']), 'receipt': copy.deepcopy(value['receipt']),
           'action': copy.deepcopy(value['next_action']), 'sync': None, 'recheck': copy.deepcopy(value['recheck']),
           'matched': False, 'gate_certified': False, 'deadline_guaranteed': False,
           'waiting_record': copy.deepcopy(value['waiting_record']), 'owner': copy.deepcopy(value['owner']),
           'claimed_run_id': previous.get('claimed_run_id', previous['work']['run_id']) if previous else value['work']['run_id'],
           'claimed_started_at': previous.get('claimed_started_at', previous['work']['started_at']) if previous else value['work']['started_at'],
           'evidence_history': history, 'evidence_conflicts': conflicts,
           'input_digest': preparation.digest(value), 'facts_digest': preparation.digest(facts)}

    def stop(reason):
        out['reason'] = reason
        return out

    if facts.get('fetch_error'):
        return stop('GitHub retrieval failed; cached success is not current evidence')
    try:
        pull, policy, issue = facts['pr'], facts['policy'], facts['issue']
        if (policy['purpose'] != PURPOSE or policy['owner'] != value['owner']
                or policy['dispatch_owners']['implementation_task'] != 'Work(root)'
                or policy['dispatch_owners']['fix_task'] != 'Work(root)'
                or policy['dispatch_owners']['local_main_sync'] != '.github/workflows/pull-local-main.yml'
                or issue['number'] != value['issue'] or 'pull_request' in issue
                or not author_matches(issue.get('user'), value['owner'])
                or re.search(r'(?m)^purpose:\s*`?' + re.escape(PURPOSE) + r'`?\s*$', issue.get('body', '')) is None
                or pull['number'] != value['pr'] or pull['base']['repo']['full_name'] != REPOSITORY
                or pull['base']['ref'] != 'main' or pull['merged'] is not True
                or not author_matches(pull['merged_by'], value['owner'])
                or pull['head']['sha'] != value['reviewed_head_sha']
                or pull['merge_commit_sha'] != value['merge_sha'] or facts['main_sha'] != value['target_main_sha']
                or not references(pull.get('body'), value['issue'])):
            return stop('Current repository/Issue/purpose/owner/PR/merge/main binding mismatch')
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
    out.update(matched=True, stage='実装済み')
    try:
        review, _ = work_review(facts['pr_comments'], value['issue'], value['pr'], value['reviewed_head_sha'], policy)
        if review['status'] != 'PASS' or value['work']['automation_id'] == policy['work_automation_id']:
            return stop('Independent reviewed HEAD is unconfirmed or reviewer is acting as resume owner')
    except (KeyError, TypeError, ValueError):
        return stop('Independent review facts are missing or invalid')
    if out['claimed_run_id'] != value['work']['run_id']:
        return stop('Different Work run already observed for this dedup key; reconcile shared ownership')
    if previous:
        if out['claimed_started_at'] != value['work']['started_at']:
            return stop('Work start identity changed')
    observations = {field: value['next_action'] if field == 'action' else value[field]
                    for field in ('event', 'work', 'claim', 'receipt', 'action', 'recheck')}
    out['attempted_evidence'] = copy.deepcopy(observations)

    def reject_evidence(reason):
        # Retain the accepted current-view fields too (Work(root)'s minimal R1
        # repair), while keeping the rejected attempt separately inspectable.
        for field, record in history.items():
            if field in out:
                out[field] = copy.deepcopy(record)
        return stop(reason)

    for field, current in observations.items():
        prior = history.get(field)
        if current is None:
            continue
        observed_at = instant(current['observed_at'])
        if field in conflicts and observed_at <= instant(conflicts[field]):
            return reject_evidence('Conflicting evidence requires a newer authenticated observation')
        if prior:
            if observed_at < instant(prior['observed_at']):
                return reject_evidence('Late observation must not roll back newer Work evidence')
            if observed_at == instant(prior['observed_at']) and current != prior:
                conflicts[field] = current['observed_at']
                return reject_evidence('Different Work evidence at the same observation time')
    claim = value['claim']
    if claim is None:
        return stop('Single-owner claim missing; no next operation')
    if instant(claim['observed_at']) < instant(value['work']['started_at']):
        return stop('Shared claim predates this Work start')
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
    if value['receipt'] is None:
        return stop('Work receipt of the exact prior waiting record is missing')
    receipt_time = instant(value['receipt']['observed_at'])
    action = value['next_action']
    if (receipt_time < instant(claim['observed_at'])
            or (action is not None and instant(action['observed_at']) < receipt_time)):
        return stop('Receipt/next operation predates the owner claim or receipt')
    # The history contains bound observations, including newer negative results.
    # A rejected attempt stays in the current view but never lowers this history.
    # Updating history is not an execution/success certification.
    for field, current in observations.items():
        if current is not None:
            history[field] = copy.deepcopy(current)
            conflicts.pop(field, None)
    if claim['status'] != 'RUNNING':
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
    if (receipt_time < instant(claim['observed_at']) or action_time < receipt_time
            or run is None or not run.get('updated_at')
            or action_time < instant(run['updated_at'])):
        return stop('Receipt/next operation predates Work start or formal sync completion')
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
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--github-read', action='store_true')
    sources.add_argument('--fixture-facts', type=Path, help='Synthetic testing only; cannot certify live results')
    args = parser.parse_args()
    value = validate(preparation.loads(args.handoff.read_text(encoding='utf-8')))
    with preparation.state_lock(args.state):
        old = preparation.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else None
        try:
            if args.github_read:
                api = ObservationGitHub(os.environ['GH_TOKEN'])
                facts = read_facts(api, value)
                if preparation.digest(facts) != preparation.digest(read_facts(api, value)):
                    raise ValueError('External facts changed during observation')
            else:
                facts = preparation.loads(args.fixture_facts.read_text(encoding='utf-8'))
            out = observe(value, facts, old)
        except (OSError, KeyError, TypeError, ValueError) as error:
            # Preserve history and invalidate cached success; never retry a mutation.
            out = observe(value, {'fetch_error': True}, old)
            out['reason'] = 'Current fact collection failed: ' + type(error).__name__
        out['source'] = 'github-read + explicit Work observations' if args.github_read else 'synthetic fixture'
        if not args.github_read:
            out['stage'] = '実装済み'
            if out['status'] == 'OBSERVED':
                out['status'] = 'FIXTURE_ONLY'
        if old == out:
            print('NO_OP (same observation; no dispatch or success promotion)')
        else:
            save_observation(args.state, out)
            print(preparation.canonical(out))
        return 0 if out['status'] in {'OBSERVED', 'FIXTURE_ONLY', 'WAITING'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
