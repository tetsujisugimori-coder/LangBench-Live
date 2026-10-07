#!/usr/bin/env python3
"""Development startup preparation: pure generation, atomic cache, read-only resume.

No dispatch/Work API or GitHub writes. Trusted-main owns shared persistence.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

try:
    from tools.automation_dashboard import REPOSITORY, sha, author_matches
except ModuleNotFoundError:
    from automation_dashboard import REPOSITORY, sha, author_matches

PURPOSE = 'automation-startup-preparation'  # Example purpose; not an input constraint
ACTIONS = {'issue', 'review', 'policy_pr', 'implementation_task', 'fix_task'}
REQUIREMENTS = {'windows_validation', 'windows_measurement', 'artifact_integrity',
                'measurement_result_pr', 'live_smoke'}
STAGES = ('issue', 'review', 'policy', 'dashboard', 'publication')
INPUT_FIELDS = {'schema_version', 'repository', 'issue', 'purpose', 'input_version',
                'start_main_sha', 'specification', 'owner', 'work_author',
                'work_automation_id', 'actors', 'requirements', 'requirement_reasons'}
ACTORS = {'implementation', 'publication', 'dispatch', 'review', 'sync'}
DEPENDENCIES = {
    'issue': ('repository', 'issue', 'purpose', 'specification', 'owner'),
    'review': ('repository', 'issue', 'purpose', 'owner', 'actors', 'work_author', 'work_automation_id', 'start_main_sha'),
    'policy': tuple(INPUT_FIELDS - {'schema_version', 'input_version'}),
    'dashboard': ('repository', 'issue', 'purpose', 'owner', 'start_main_sha', 'requirements'),
    'publication': ('repository', 'issue', 'purpose', 'actors', 'start_main_sha', 'specification'),
}
REQUEST_START = '<!-- langbench-preparation-input:v1\n'
REQUEST_END = '\nlangbench-preparation-input:end -->'
SNAPSHOT_START = '<!-- langbench-preparation-snapshot:v1\n'
SNAPSHOT_END = '\nlangbench-preparation-snapshot:end -->'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def loads(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def identity(value):
    if (not isinstance(value, dict) or set(value) != {'login', 'id', 'type'}
            or not isinstance(value['login'], str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', value['login'])
            or type(value['id']) is not int or value['id'] <= 0 or value['type'] != 'User'):
        raise ValueError('Invalid formal identity')


def validate_input(value):
    if not isinstance(value, dict) or set(value) != INPUT_FIELDS:
        raise ValueError('Unknown/missing input fields')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['repository'] != REPOSITORY
            or (value['issue'] is not None and (type(value['issue']) is not int or value['issue'] <= 0))
            or not isinstance(value['purpose'], str) or re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value['purpose']) is None
            or not sha(value['start_main_sha'])
            or type(value['input_version']) is not int or value['input_version'] <= 0):
        raise ValueError('Invalid input scope/version/SHA')
    identity(value['owner']); identity(value['work_author'])
    for key in ('specification',):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 10000:
            raise ValueError('Missing specification reference')
    automation = value['work_automation_id']
    if automation is not None and (not isinstance(automation, str) or not re.fullmatch(r'[a-f0-9]{32}', automation)):
        raise ValueError('Invalid automation ID')
    if not isinstance(value['actors'], dict) or set(value['actors']) != ACTORS or any(
            not isinstance(v, str) or not v.strip() for v in value['actors'].values()):
        raise ValueError('Missing actor')
    if (not isinstance(value['requirements'], dict) or set(value['requirements']) != REQUIREMENTS
            or any(v not in ('REQUIRED', 'NOT_REQUIRED') for v in value['requirements'].values())
            or not isinstance(value['requirement_reasons'], dict) or set(value['requirement_reasons']) != REQUIREMENTS
            or any(not isinstance(v, str) or not v.strip() for v in value['requirement_reasons'].values())):
        raise ValueError('Missing/invalid requirement or rationale')
    canonical(value)
    return value


def policy_entry(value):
    validate_input(value)
    if value['work_automation_id'] is None:
        raise ValueError('Review registration ID unavailable; policy cannot be registered')
    return {'purpose': value['purpose'], 'owner': copy.deepcopy(value['owner']),
            'work_author': copy.deepcopy(value['work_author']),
            'work_automation_id': value['work_automation_id'], 'dashboard_comment_id': None,
            'initial_dispatch': None, 'requirements': copy.deepcopy(value['requirements']),
            'dispatch_owners': {'implementation_task': value['actors']['dispatch'],
                                'fix_task': value['actors']['dispatch'],
                                'work_review': value['actors']['review'],
                                'local_main_sync': value['actors']['sync']}}


def policy_diff(value, config):
    if (type(config.get('schema_version')) is not int or config.get('schema_version') != 1 or config.get('repository') != REPOSITORY
            or not isinstance(config.get('issues'), dict)):
        raise ValueError('Invalid existing policy configuration')
    if value['issue'] is None:
        raise ValueError('Issue ID unavailable; policy registration must wait')
    proposed = policy_entry(value)
    existing = config['issues'].get(str(value['issue']))
    if existing is not None and existing != proposed:
        raise ValueError('Conflicting policy registration')
    return {'schema_version': 1, 'repository': REPOSITORY,
            'issues': {} if existing is not None else {str(value['issue']): proposed}}


def empty_stage():
    return {'status': 'UNCONFIRMED', 'evidence': None, 'observed_at': None,
            'waiting_reason': 'Fresh external confirmation required', 'check_target': None}


def new_state(value):
    validate_input(value)
    return {'schema_version': 1, 'kind': 'startup_preparation', 'input': copy.deepcopy(value),
            'input_digest': digest(value), 'stages': {k: empty_stage() for k in STAGES},
            'operations': {}, 'input_history': [], 'owner_observations': {},
            'last_progress_at': None, 'last_observed_at': None,
            'next_owner': value['actors']['dispatch'], 'next_action': 'Work(root) must verify the Issue and review registration',
            'status': 'UNCONFIRMED', 'gate_scope': 'Separate; no Merge/Completion certification',
            'shared_persistence': False}


def timestamp(value):
    if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Observation must have timezone')


def external_id(value):
    return ((type(value) is int and value > 0) or
            (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) is not None))


def validate_state(state):
    if not isinstance(state, dict) or 'input' not in state:
        raise ValueError('Broken preparation state')
    template = new_state(state['input'])
    if (set(state) not in (set(template), set(template) - {'owner_observations'}) or type(state['schema_version']) is not int or state['schema_version'] != 1
            or state['kind'] != template['kind'] or state['input_digest'] != digest(state['input'])
            or set(state['stages']) != set(STAGES) or not isinstance(state['operations'], dict)
            or state['gate_scope'] != template['gate_scope'] or type(state['shared_persistence']) is not bool
            or state['status'] not in {'UNCONFIRMED', 'WAITING', 'PREPARATION_COMPLETE', 'STOPPED'}):
        raise ValueError('Broken preparation schema/digest')
    for stage in state['stages'].values():
        if (not isinstance(stage, dict) or set(stage) != set(empty_stage())
                or stage['status'] not in {'UNCONFIRMED', 'CONFIRMED', 'WAITING', 'UNKNOWN', 'INVALIDATED'}
                or (stage['status'] == 'CONFIRMED' and not isinstance(stage['evidence'], dict))):
            raise ValueError('Broken stage evidence')
        if stage['observed_at'] is not None: timestamp(stage['observed_at'])
    observations = state.get('owner_observations', {})
    if not isinstance(observations, dict) or set(observations) - {'review', 'publication'}:
        raise ValueError('Broken owner observation history')
    for observation in observations.values():
        if (not isinstance(observation, dict) or set(observation) != {'input_digest', 'observed_at'}
                or observation['input_digest'] != state['input_digest']):
            raise ValueError('Owner observation input binding differs from current input')
        timestamp(observation['observed_at'])
    for key, operation in state['operations'].items():
        if (not isinstance(key, str) or re.fullmatch(re.escape(REPOSITORY) + r':issue(null|[1-9][0-9]*):[0-9a-f]{40}:(issue|review|policy_pr|implementation_task|fix_task):[A-Za-z0-9_-]{1,100}', key) is None or not isinstance(operation, dict)
                or set(operation) != {'status', 'external_id', 'input_digest'}
                or operation['status'] not in {'UNKNOWN', 'CONFIRMED'}
                or not re.fullmatch('[0-9a-f]{64}', operation['input_digest'])
                or (operation['status'] == 'CONFIRMED' and not external_id(operation['external_id']))
                or (operation['status'] == 'UNKNOWN' and operation['external_id'] is not None)
                or (operation['input_digest'] == state['input_digest']
                    and key not in {operation_key(state['input'], a) for a in ACTIONS})):
            raise ValueError('Broken operation dedup ledger')
    if not isinstance(state['input_history'], list):
        raise ValueError('Broken input transition history')
    previous_version = 0
    for old in state['input_history']:
        validate_input(old)
        if (old['repository'] != state['input']['repository'] or old['purpose'] != state['input']['purpose']
                or old['owner'] != state['input']['owner'] or old['input_version'] <= previous_version
                or old['input_version'] >= state['input']['input_version']
                or old['issue'] not in (None, state['input']['issue'])):
            raise ValueError('Unrelated or unordered input transition history')
        previous_version = old['input_version']
    known_inputs = {digest(v): v for v in state['input_history'] + [state['input']]}
    for key, operation in state['operations'].items():
        bound = known_inputs.get(operation['input_digest'])
        if bound is None or key not in {operation_key(bound, a) for a in ACTIONS}:
            raise ValueError('Operation lacks authenticated input history')
    for k in ('last_progress_at', 'last_observed_at'):
        if state[k] is not None: timestamp(state[k])
    for k in ('next_owner', 'next_action'):
        if not isinstance(state[k], str) or not state[k]: raise ValueError('Missing next action')
    if state['status'] == 'PREPARATION_COMPLETE' and (
            any(s['status'] != 'CONFIRMED' for s in state['stages'].values())
            or any(o['status'] != 'CONFIRMED' for o in state['operations'].values())):
        raise ValueError('Preparation completion lacks all current facts')
    canonical(state)
    return state


def rebase(state, value):
    validate_state(state); validate_input(value)
    if value == state['input']: return copy.deepcopy(state)
    if value['input_version'] <= state['input']['input_version']:
        raise ValueError('Old version or changed input without new version')
    output = copy.deepcopy(state)
    # A different input version requires freshly bound owner evidence.
    output['owner_observations'] = {}
    output['input_history'].append(copy.deepcopy(state['input']))
    for name, dependencies in DEPENDENCIES.items():
        if any(state['input'][k] != value[k] for k in dependencies):
            output['stages'][name] = {**empty_stage(), 'status': 'INVALIDATED',
                                      'waiting_reason': 'Affected input changed; old evidence invalidated'}
    output.update(input=copy.deepcopy(value), input_digest=digest(value), status='UNCONFIRMED',
                  next_owner=value['actors']['dispatch'], next_action='Work(root) must recheck affected preparation evidence')
    # Keep all unknown operations across input changes. They cannot authorize retransmission.
    return output


def operation_key(value, action):
    return f"{value['repository']}:issue{value['issue'] if value['issue'] is not None else 'null'}:{value['start_main_sha']}:{action}:{value['purpose']}"


def mark_unknown(state, action):
    """Persist BEFORE handing an explicit request to its external owner."""
    validate_state(state)
    if action not in ACTIONS:
        raise ValueError('Unsupported preparation operation')
    key = operation_key(state['input'], action)
    if key in state['operations'] or any(
            o['status'] == 'UNKNOWN' and f':{action}:' in k for k, o in state['operations'].items()):
        raise ValueError('Existing/unknown operation; reconcile externally, never resend')
    output = copy.deepcopy(state)
    output['operations'][key] = {'status': 'UNKNOWN', 'external_id': None, 'input_digest': state['input_digest']}
    output.update(status='WAITING', next_owner=state['input']['actors']['dispatch'],
                  next_action='External owner must reconcile unknown send outcome; no retransmission')
    return output


def resume(state, facts, observed_at):
    """Facts come from current read-only adapter, never saved cached PASS."""
    validate_state(state); timestamp(observed_at)
    value = state['input']
    if facts.get('input_digest') != state['input_digest']:
        raise ValueError('Facts are for another input version')
    observations = copy.deepcopy(state.get('owner_observations', {}))
    # Read pre-watermark v1 caches without losing their most recent observation.
    if 'owner_observations' not in state:
        for name in ('review', 'publication'):
            evidence = state['stages'][name]['evidence'] or {}
            if evidence.get('owner_observed_at'):
                observations[name] = {'input_digest': state['input_digest'],
                                      'observed_at': evidence['owner_observed_at']}
    for name in ('review', 'publication'):
        current = facts.get(name) or {}
        if current.get('owner_observed_at'):
            timestamp(current['owner_observed_at'])
            prior = observations.get(name)
            if prior and datetime.fromisoformat(current['owner_observed_at'].replace('Z', '+00:00')) < datetime.fromisoformat(prior['observed_at'].replace('Z', '+00:00')):
                raise ValueError('Older owner observation cannot roll back current evidence')
            observations[name] = {'input_digest': state['input_digest'],
                                  'observed_at': current['owner_observed_at']}
    output = copy.deepcopy(state)
    output['owner_observations'] = observations
    output['stages'] = {k: empty_stage() for k in STAGES}
    def observe(name, status, evidence, reason, target):
        output['stages'][name] = {'status': status, 'evidence': evidence,
            'observed_at': observed_at, 'waiting_reason': reason, 'check_target': target}
    issue = facts.get('issue')
    if issue:
        if (type(issue.get('number')) is not int or issue['number'] <= 0 or issue.get('number') != value['issue'] or issue.get('repository') != value['repository']
                or issue.get('purpose') != value['purpose'] or not author_matches(issue.get('owner'), value['owner'])):
            raise ValueError('External Issue scope/owner mismatch')
        observe('issue', 'CONFIRMED', issue, None, issue['number'])
    review = facts.get('review')
    if review:
        if review.get('available') is False:
            observe('review', 'UNKNOWN', review, 'Work review evidence was unavailable at the recorded observation', review.get('evidence_ref'))
        else:
            if review.get('id') != value['work_automation_id']: raise ValueError('Review automation mismatch')
            observe('review', 'CONFIRMED' if review.get('enabled') is True and review.get('event_verified') is True else 'WAITING',
                    review, None if review.get('enabled') is True and review.get('event_verified') is True
                    else 'Registration/enabled and real event must both be verified', review.get('id'))
    main = facts.get('main_policy')
    proposal = policy_entry(value) if value['work_automation_id'] is not None else None
    if main is not None:
        if main != proposal: raise ValueError('Trusted-main policy differs from input')
        if not sha(facts.get('main_sha')): raise ValueError('Missing trusted-main readback SHA')
        observe('policy', 'CONFIRMED', {'main_sha': facts['main_sha'], 'policy': main}, None, facts['main_sha'])
    elif facts.get('policy_pr'):
        pr = facts['policy_pr']
        observe('policy', 'WAITING', pr, 'Merged PR still requires trusted-main readback' if pr.get('merged') else 'Human merge pending', pr.get('number'))
    dash = facts.get('dashboard')
    if dash:
        if (dash.get('repository'), dash.get('issue'), dash.get('purpose')) != (value['repository'], value['issue'], value['purpose']):
            raise ValueError('Dashboard scope mismatch')
        if type(dash.get('comment_id')) is not int or dash['comment_id'] <= 0: raise ValueError('Missing Dashboard ID')
        observe('dashboard', 'CONFIRMED', dash, None, dash['comment_id'])
    else:
        observe('dashboard', 'WAITING', None, '正式Dashboard未適用', None)
    publication = facts.get('publication')
    if publication:
        if publication.get('available') is True:
            observe('publication', 'CONFIRMED', publication, None, publication.get('primary_route'))
        elif publication.get('available') is False:
            observe('publication', 'UNKNOWN', publication, 'Publication route was unavailable at the recorded observation', publication.get('evidence_ref'))
    for key, operation in output['operations'].items():
        external = facts.get('operations', {}).get(key)
        if external is not None:
            if (not isinstance(external, dict) or set(external) != {'id', 'input_digest'}
                    or external['input_digest'] != operation['input_digest'] or not external_id(external['id'])):
                raise ValueError('Operation identity is not reconciled')
            operation.update(status='CONFIRMED', external_id=external['id'])
    pending = [k for k in STAGES if output['stages'][k]['status'] != 'CONFIRMED']
    unknown = any(x['status'] == 'UNKNOWN' for x in output['operations'].values())
    if unknown:
        owner, action = value['actors']['dispatch'], 'Reconcile unknown send outcome; retransmission prohibited'
    elif 'issue' in pending:
        owner, action = value['actors']['dispatch'], 'Work(root) must verify the formal Issue'
    elif 'review' in pending:
        owner, action = value['actors']['dispatch'], 'Work(root) must verify review registration and the real event'
    elif 'policy' in pending and facts.get('policy_pr'):
        if facts['policy_pr'].get('merged') is True:
            owner, action = value['actors']['dispatch'], 'Work(root) must read back merged policy on trusted main'
        else:
            owner, action = 'human merge owner', 'Human merge is required; then Work(root) must read back trusted main'
    elif 'policy' in pending:
        owner, action = value['actors']['dispatch'], 'Work(root) must publish and verify the formal policy path'
    elif 'dashboard' in pending:
        owner, action = value['actors']['dispatch'], 'Work(root) must verify the formal dashboard'
    elif 'publication' in pending:
        owner, action = value['actors']['publication'], 'Formal publication owner must verify primary and recovery routes'
    else:
        owner, action = value['actors']['implementation'], 'Preparation confirmed; implementation may be started separately'
    output.update(status='PREPARATION_COMPLETE' if not pending and not unknown else 'WAITING',
                  next_owner=owner, next_action=action)
    # Repeated observation is NO_OP: timestamp does not masquerade as progress.
    comparable = copy.deepcopy(output)
    for name in STAGES:
        comparable['stages'][name]['observed_at'] = state['stages'][name]['observed_at']
    if comparable != state:
        output['last_progress_at'] = observed_at
        output['last_observed_at'] = observed_at
        return output
    return copy.deepcopy(state)


@contextmanager
def state_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('State is locked; after interruption inspect operation ledger before manual unlock') from exc
    try:
        os.write(descriptor, str(os.getpid()).encode()); os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor); lock.unlink()


def atomic_save(path, state):
    validate_state(state)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    # Reject damaged prior files rather than silently replace their evidence.
    if path.exists(): validate_state(loads(path.read_text(encoding='utf-8')))
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(canonical(state) + '\n'); handle.flush(); os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True); raise
    try:
        os.replace(temporary, path)
        if os.name == 'posix':
            descriptor = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def summary(state):
    validate_state(state)
    dashboard = state['stages']['dashboard']['evidence']
    return '\n'.join([
        f"Issue #{state['input']['issue'] if state['input']['issue'] is not None else 'null'} / {state['input']['purpose']} / input v{state['input']['input_version']}",
        'Preparation: ' + state['status'],
        *[f"{k}: {s['status']} — {s['waiting_reason'] or 'external fact confirmed'}" for k, s in state['stages'].items()],
        '正式Dashboard: ' + (str(dashboard['comment_id']) if dashboard else '正式Dashboard未適用'),
        'Next owner: ' + state['next_owner'], 'Next action: ' + state['next_action'],
        'Preparation / AUTOMATION_ARMED / implementation / Merge / Completion PASS are separate.',
        '機械Merge Gate未認定。Completion未認定。独立PASS・dispatch receiptは生成しない。',
        '期限保証不能。Work登録/実イベント・Cloud起動・正式同期との自動接続は未実装。',
        'GitHub trusted-main shared record' if state['shared_persistence'] else 'Local cache only; not shared between environments.',
    ]) + '\n'


def generate(value, config, state=None, owner_facts=None):
    validate_input(value)
    if owner_facts is not None:
        try:
            from tools.preparation_github import validate_owner_facts
        except ModuleNotFoundError:
            from preparation_github import validate_owner_facts
        validate_owner_facts(owner_facts, value)
    state = rebase(state, value) if state else new_state(value)
    return {'issue_body.md': f"## 開始準備\nrepository: {value['repository']}\npurpose: {value['purpose']}\n開始main: {value['start_main_sha']}\n仕様参照: {value['specification']}\n承認参照だけで承認認定しない。\n\n" + canonical(value) + '\n',
            'review_registration.md': f"Work(root) による独立登録・読戻し・実イベント確認が必要。\nIssue #{value['issue'] if value['issue'] is not None else 'null'} / {value['purpose']}\n担当: {value['actors']['review']}\nautomation_id: {value['work_automation_id'] or 'null'}\n別実行のコード・設定レビュー。実装担当は独立PASSを代筆しない。\n",
            'policy_diff.json': canonical(policy_diff(value, config)) + '\n' if value['work_automation_id'] and value['issue'] is not None else 'null\n',
            'preparation.json': canonical(state) + '\n', 'summary.md': summary(state),
            'github_record.md': REQUEST_START + canonical({'schema_version': 1, 'kind': 'startup_preparation_input',
                'repository': value['repository'], 'issue': value['issue'], 'purpose': value['purpose'],
                'owner': value['owner'], 'input_version': value['input_version'], 'input_digest': digest(value),
                'input': value, 'input_history': state['input_history'], 'owner_facts': owner_facts,
                'operations': {k: {**v, 'status': 'UNKNOWN', 'external_id': None}
                    for k, v in state['operations'].items()}}) + REQUEST_END + '\n'}


def main():
    # Machine-readable artifacts and captured summaries share one encoding on Windows/Linux.
    if getattr(sys.stdout, 'reconfigure', None):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('.github/automation-dashboard.json'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--github-read', action='store_true', help='Read public GitHub facts; never writes')
    parser.add_argument('--owner-facts', type=Path, help='Formal owner observations; never fetched from a private Work API')
    parser.add_argument('--mark-unknown', choices=('issue', 'review', 'policy_pr', 'implementation_task', 'fix_task'))
    args = parser.parse_args()
    value = validate_input(loads(args.input.read_text(encoding='utf-8')))
    config = loads(args.config.read_text(encoding='utf-8'))
    with state_lock(args.state):
        old = validate_state(loads(args.state.read_text(encoding='utf-8'))) if args.state.exists() else None
        state = rebase(old, value) if old else new_state(value)
        if args.mark_unknown: state = mark_unknown(state, args.mark_unknown)
        owner_facts = loads(args.owner_facts.read_text(encoding='utf-8')) if args.owner_facts else None
        try:
            from tools.preparation_github import apply_owner_facts
        except ModuleNotFoundError:
            from preparation_github import apply_owner_facts
        facts = apply_owner_facts({'input_digest': digest(value)}, owner_facts, value)
        if args.github_read:
            try:
                from tools.preparation_github import read_facts
                from tools.preparation_github import reconcile_operations
                from tools.update_automation_dashboard import GitHub
            except ModuleNotFoundError:
                from preparation_github import read_facts
                from preparation_github import reconcile_operations
                from update_automation_dashboard import GitHub
            try:
                api = GitHub(os.environ['GH_TOKEN'])
                facts = apply_owner_facts(read_facts(api, value), owner_facts, value)
                if value['issue'] is not None:
                    facts['operations'] = reconcile_operations(api, value['issue'], policy_entry(value), state, facts)
                state = resume(state, facts, datetime.now(timezone.utc).isoformat())
            except (OSError, ValueError, KeyError, TypeError):
                # Keep history, but never show an old completed cache as current success.
                state.update(status='STOPPED', next_owner=value['actors']['dispatch'],
                             next_action='External facts unavailable; inspect saved evidence and reconnect; no retransmission')
                atomic_save(args.state, state)
                print(summary(state), end='')
                raise
        elif owner_facts is not None:
            state = resume(state, facts, owner_facts['observed_at'])
        elif old is not None:
            # No current facts were supplied; preserve history, not cached confirmation.
            state = resume(state, facts, datetime.now(timezone.utc).isoformat())
        products = generate(value, config, state, owner_facts)
        atomic_save(args.state, state)
        args.output.mkdir(parents=True, exist_ok=True)
        for name, content in products.items():
            (args.output / name).write_text(content, encoding='utf-8')
        print(summary(state), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
