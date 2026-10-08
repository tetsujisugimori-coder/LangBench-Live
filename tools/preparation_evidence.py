"""Opt-in I-01 shared preparation contract v2, consumed by the existing CLI/writer.

GitHub author authentication is performed by preparation_github. Saved Work
settings are owner attestations from the supported UI/tool, not service proofs.
No registration, dispatch, private API, merge or cross-environment lease.
"""
from __future__ import annotations
import copy
from datetime import datetime
try:
    from tools import startup_preparation as p
except ModuleNotFoundError:
    import startup_preparation as p

PHASES = ('PRE_IMPLEMENTATION', 'PR_BOUND', 'PRE_MERGE', 'POST_MERGE', 'FINISHED')
INPUT_FIELDS = p.INPUT_FIELDS | {'phase', 'pr', 'head_sha', 'owner_resume_id', 'registration_prompts'}
ROLES = ('review', 'owner_resume')
STATUSES = {'NOT_ATTEMPTED', 'ATTEMPTING', 'REGISTERED', 'SETTINGS_CONFIRMED',
            'FAILED', 'UNKNOWN', 'DISABLED_CONFIRMED'}
UNRESOLVED = {'UNKNOWN', 'ATTEMPTING'}
REQUEST_START = '<!-- langbench-preparation-input:v2\n'
SNAPSHOT_START = '<!-- langbench-preparation-snapshot:v2\n'
FACT_FIELDS = {'schema_version', 'repository', 'issue', 'purpose', 'owner', 'input_version',
              'input_digest', 'start_main_sha', 'observed_at', 'review', 'owner_resume',
              'publication', 'waiting_record', 'execution', 'completion_observation', 'stop'}
REG_FIELDS = {'status', 'id', 'settings_version', 'observed_at', 'settings', 'event', 'observation'}
LEDGER_FIELDS = {'role', 'pr', 'head_sha', 'input_digest', 'status', 'external_id',
                 'settings_version', 'observed_at'}


def instant(value):
    p.timestamp(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('Unknown/missing ' + label + ' fields')


def positive(value):
    return type(value) is int and value > 0


def text(value):
    return isinstance(value, str) and bool(value.strip())


def legacy_input(value):
    return {**{k: copy.deepcopy(value[k]) for k in p.INPUT_FIELDS}, 'schema_version': 1}


def validate_input(value):
    fields(value, INPUT_FIELDS, 'v2 input')
    p.validate_input(legacy_input(value))
    if (type(value['schema_version']) is not int or value['schema_version'] != 2
            or value['purpose'] != 'work-owner-resume-i01' or not positive(value['issue'])
            or value['phase'] not in PHASES):
        raise ValueError('Invalid v2 contract scope/phase')
    if value['phase'] == 'PRE_IMPLEMENTATION':
        if value['pr'] is not None or value['head_sha'] is not None or value['owner_resume_id'] is not None:
            raise ValueError('Pre-implementation must not invent PR/HEAD/resume ID')
    elif not positive(value['pr']) or not p.sha(value['head_sha']):
        raise ValueError('Actual PR/full HEAD required')
    ident = value['owner_resume_id']
    if ident is not None and (not isinstance(ident, str) or not p.re.fullmatch('[a-f0-9]{32}', ident)
                             or ident == value['work_automation_id']):
        raise ValueError('Resume registration must have a distinct real ID')
    fields(value['registration_prompts'], set(ROLES), 'approved Prompt expectations')
    for role, expected in value['registration_prompts'].items():
        if expected is None:
            continue
        fields(expected, {'version', 'text', 'digest'}, 'approved Prompt')
        if not positive(expected['version']) or not text(expected['text']) or expected['digest'] != p.hashlib.sha256(expected['text'].encode('utf-8')).hexdigest():
            raise ValueError('Approved Prompt version/full UTF-8 digest invalid')
    return value


def policy_entry(value):
    validate_input(value)
    return {**p.policy_entry(legacy_input(value)), 'preparation_contract': 2}


def prompt(value, role):
    """Exact auditable Prompt template; outer Trigger is checked independently."""
    validate_input(value)
    if role not in ROLES: raise ValueError('Unknown role')
    return (f"repository: {value['repository']}\nIssue: {value['issue']}\npurpose: {value['purpose']}\n"
            f"role: {role}\nowner: {value['actors']['dispatch']}\nPR: {value['pr']}\n"
            f"reviewed HEAD: {value['head_sha']}\n"
            + ('Independent Work review; verify current full HEAD and report only this PR.\n'
               if role == 'review' else
               'Work(root) merge resume: re-fetch Issue/PR/policy/Dashboard/main; reject stale or unmerged events.\n'
               'Authenticate the shared waiting record and exclusive claim before receipt or next operation.\n'
               'Read the existing pull-local-main.yml run; never dispatch/rerun sync. Verify exact SHA, actual ZIP/digest/report and preservation.\n'
               'If pending, continue this execution or verify a pending-only recheck registration.\n'
               'Execute only the authorized live smoke/safe stop; update owner input, read sole-writer result and remaining Completion.\n'
               'Never edit snapshots/Gates, auto-merge, start another theme or claim an unobserved Work event.\n'))


def validate_registration(record, value, role):
    fields(record, REG_FIELDS, 'registration')
    if record['status'] not in STATUSES: raise ValueError('Invalid registration status')
    instant(record['observed_at'])
    ident = record['id']
    expected = value['work_automation_id'] if role == 'review' else value['owner_resume_id']
    if ident is not None and (ident != expected or not isinstance(ident, str)
                              or not p.re.fullmatch('[a-f0-9]{32}', ident)):
        raise ValueError('Role/ID differs from authenticated input')
    if record['settings_version'] is not None and not positive(record['settings_version']):
        raise ValueError('Invalid settings revision')
    fields(record['observation'], {'method', 'evidence_ref'}, 'settings observation')
    if record['observation']['method'] not in {'official_ui', 'official_tool'} or not text(record['observation']['evidence_ref']):
        raise ValueError('Saved settings require a supported owner observation')
    settings = record['settings']
    if settings is not None:
        fields(settings, {'enabled', 'trigger', 'prompt'}, 'saved settings')
        fields(settings['trigger'], {'repository', 'pr', 'events', 'only_on_merge', 'title_match'}, 'saved Trigger')
        trigger = settings['trigger']
        if (type(settings['enabled']) is not bool or not text(settings['prompt'])
                or not isinstance(trigger['events'], list) or not trigger['events']
                or len(set(trigger['events'])) != len(trigger['events'])
                or any(e not in {'opened', 'ready', 'closed', 'synchronize', 'review', 'comment'} for e in trigger['events'])
                or type(trigger['only_on_merge']) is not bool
                or trigger['title_match'] is not None and not isinstance(trigger['title_match'], str)):
            raise ValueError('Partial or malformed saved settings')
    if record['status'] in {'REGISTERED', 'SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'} and ident is None:
        raise ValueError('Registration result needs a real ID')
    if record['status'] in {'SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'} and (settings is None or record['settings_version'] is None):
        raise ValueError('Partial readback cannot confirm settings')
    if record['status'] == 'NOT_ATTEMPTED' and (ident is not None or settings is not None):
        raise ValueError('Not-attempted cannot assert a saved registration')
    event = record['event']
    if event is not None:
        fields(event, {'id', 'pr', 'head_sha', 'observed_at', 'evidence_ref'}, 'actual event')
        if (not text(event['id']) or event['pr'] != value['pr'] or not positive(event['pr'])
                or event['head_sha'] != value['head_sha'] or not text(event['evidence_ref'])):
            raise ValueError('Actual event does not bind the current PR/HEAD')
        if instant(event['observed_at']) > instant(record['observed_at']):
            raise ValueError('Event is after settings observation')
    return record


def ready(record, value, role, stopped=False):
    if not record: return False
    settings = record['settings']
    expected_status = 'DISABLED_CONFIRMED' if stopped else 'SETTINGS_CONFIRMED'
    if record['status'] != expected_status or settings is None: return False
    trigger = settings['trigger']
    return (record['id'] is not None and record['settings_version'] is not None
            and settings['enabled'] is (False if stopped else True)
            and trigger['repository'] == value['repository'] and trigger['pr'] == value['pr']
            and trigger['title_match'] == (f"^Issue #{value['issue']}:" if value['pr'] is None else None)
            and value['registration_prompts'][role] is not None
            and record['settings_version'] >= value['registration_prompts'][role]['version']
            and settings['prompt'] == value['registration_prompts'][role]['text']
            and (trigger['events'] == ['closed'] and trigger['only_on_merge'] is True
                 if role == 'owner_resume' else trigger['only_on_merge'] is False))


def validate_owner_facts(record, value):
    validate_input(value); fields(record, FACT_FIELDS, 'v2 owner facts')
    for key in ('schema_version', 'repository', 'issue', 'purpose', 'owner', 'input_version', 'start_main_sha'):
        if type(record[key]) is not type(value[key]) or record[key] != value[key]:
            raise ValueError('Owner fact scope/identity/input binding mismatch')
    if record['input_digest'] != p.digest(value): raise ValueError('Owner fact digest differs')
    observed = instant(record['observed_at'])
    for role in ROLES:
        validate_registration(record[role], value, role)
        if instant(record[role]['observed_at']) > observed: raise ValueError('Future registration observation')
    publication = record['publication']
    fields(publication, {'available', 'publisher', 'primary_route', 'recovery_route', 'evidence_ref'}, 'publication')
    if (type(publication['available']) is not bool or publication['publisher'] != value['actors']['publication']
            or not text(publication['evidence_ref'])
            or any(not text(publication[k]) if publication['available'] else publication[k] is not None
                   for k in ('primary_route', 'recovery_route'))):
        raise ValueError('Invalid publication observation')
    waiting = record['waiting_record']
    if waiting is not None:
        fields(waiting, {'comment_id', 'body_sha256', 'head_sha', 'authorization_ref', 'allowed_action', 'resume_id'}, 'waiting record')
        if (not positive(waiting['comment_id']) or not isinstance(waiting['body_sha256'], str)
                or not p.re.fullmatch('[a-f0-9]{64}', waiting['body_sha256'])
                or waiting['head_sha'] != value['head_sha'] or not text(waiting['authorization_ref'])
                or waiting['allowed_action'] not in {'live_smoke', 'safe_stop'}
                or waiting['resume_id'] is None or waiting['resume_id'] != value['owner_resume_id']):
            raise ValueError('Invalid independent waiting comment binding')
    execution = record['execution']
    if execution is not None:
        try:
            from tools import work_owner_resume as resume
        except ModuleNotFoundError:
            import work_owner_resume as resume
        resume.validate(execution)
        if any(execution[k] != value[k] for k in ('repository', 'issue', 'purpose', 'owner', 'pr')) or execution['reviewed_head_sha'] != value['head_sha']:
            raise ValueError('Execution scope differs')
        if execution['work']['automation_id'] != value['owner_resume_id']:
            raise ValueError('Execution is not the resume role/ID')
        if execution['next_action'] is not None and waiting is not None and (execution['next_action']['kind'] != waiting['allowed_action'] or execution['next_action']['authorization_ref'] != waiting['authorization_ref']):
            raise ValueError('Executed next operation differs from the authorized waiting record')
        if waiting is None or execution['waiting_record'] != {k: waiting[k] for k in ('comment_id', 'body_sha256')}:
            raise ValueError('Execution receipt/waiting binding differs')
    completion = record['completion_observation']
    if completion is not None:
        fields(completion, {'dashboard_comment_id', 'merge_sha', 'observed_at', 'missing', 'evidence_ref'}, 'formal remaining-conditions observation')
        if (not positive(completion['dashboard_comment_id']) or not p.sha(completion['merge_sha'])
                or not isinstance(completion['missing'], list) or any(not text(m) for m in completion['missing'])
                or not text(completion['evidence_ref']) or instant(completion['observed_at']) > observed):
            raise ValueError('Invalid formal remaining-conditions readback')
    stop = record['stop']
    if stop is not None:
        fields(stop, {'review', 'owner_resume', 'observed_at'}, 'stop operation')
        if any(not text(stop[r]) for r in ROLES) or instant(stop['observed_at']) > observed:
            raise ValueError('Stop requests are not observed operations')
    return record


def new_state(value):
    validate_input(value)
    return {'schema_version': 2, 'kind': 'startup_preparation', 'input': copy.deepcopy(value),
            'input_digest': p.digest(value), 'input_history': [], 'legacy': p.new_state(legacy_input(value)),
            'operations': {}, 'owner_watermarks': {},
            'phase_evidence': {'phase': value['phase'], 'status': 'WAITING', 'missing': ['Fresh authenticated owner/public facts required'],
                               'i01_live': 'UNVERIFIED', 'resume_observation': None},
            'last_progress_at': None, 'last_observed_at': None,
            'next_owner': value['actors']['dispatch'], 'next_action': 'Read current owner settings and public facts',
            'status': 'WAITING', 'gate_scope': 'Phase evidence; formal Gate additionally evaluates CI/review/sync',
            'shared_persistence': False}


def op_key(value, role):
    return f"{value['repository']}:issue{value['issue']}:{value['start_main_sha']}:{role}:pr{value['pr']}:{value['purpose']}"


def validate_state(state):
    if not isinstance(state, dict) or 'input' not in state:
        raise ValueError('Missing v2 state input')
    fields(state, set(new_state(state['input'])), 'v2 state')
    value = validate_input(state['input'])
    if (type(state['schema_version']) is not int or state['schema_version'] != 2 or state['kind'] != 'startup_preparation'
            or state['input_digest'] != p.digest(value) or type(state['shared_persistence']) is not bool
            or state['gate_scope'] != new_state(value)['gate_scope'] or state['status'] not in {'WAITING', 'PHASE_EVIDENCE_COMPLETE', 'STOPPED'}):
        raise ValueError('Invalid v2 state/digest')
    p.validate_state(state['legacy'])
    if state['legacy']['input'] != legacy_input(value): raise ValueError('Legacy stage/input disagreement')
    history = state['input_history']
    if not isinstance(history, list): raise ValueError('Invalid contract migration history')
    previous_version = 0
    for old in history:
        p.validate_input(old)
        if (old['input_version'] <= previous_version or old['input_version'] >= value['input_version']
                or any(old[k] != value[k] for k in ('repository', 'purpose', 'owner'))
                or old['issue'] not in (None, value['issue']) or old['schema_version'] > 2):
            raise ValueError('Invalid ordered input history')
        previous_version = old['input_version']
    known = {p.digest(v): v for v in history + [value]}
    if not isinstance(state['operations'], dict): raise ValueError('Invalid operation ledger')
    for key, operation in state['operations'].items():
        fields(operation, LEDGER_FIELDS, 'registration operation')
        bound = known.get(operation['input_digest'])
        if (bound is None or bound['schema_version'] != 2 or operation['role'] not in {'review_bind', 'owner_resume'}
                or key != op_key(bound, operation['role']) or operation['status'] not in STATUSES
                or operation['pr'] != bound['pr'] or operation['head_sha'] != bound['head_sha']
                or operation['external_id'] is not None and (not isinstance(operation['external_id'], str)
                    or not p.re.fullmatch('[a-f0-9]{32}', operation['external_id']))):
            raise ValueError('Operation identity/input/PR binding differs')
        if operation['status'] in {'REGISTERED', 'SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'} and operation['external_id'] is None:
            raise ValueError('Successful ledger operation lacks real ID')
        if operation['status'] in {'SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'} and (operation['settings_version'] is None or operation['observed_at'] is None):
            raise ValueError('Confirmed ledger lacks saved-settings version/time')
        expected = bound['work_automation_id'] if operation['role'] == 'review_bind' else bound['owner_resume_id']
        if operation['external_id'] is not None and operation['external_id'] != expected:
            raise ValueError('Ledger role/ID mismatch')
        if operation['settings_version'] is not None and not positive(operation['settings_version']):
            raise ValueError('Invalid ledger settings version')
        if operation['observed_at'] is not None: instant(operation['observed_at'])
    if not isinstance(state['owner_watermarks'], dict) or set(state['owner_watermarks']) - (set(ROLES) | {'publication'}):
        raise ValueError('Unknown owner watermark')
    for role, watermark in state['owner_watermarks'].items():
        fields(watermark, {'input_digest', 'record', 'conflict_at'}, 'owner watermark')
        bound = known.get(watermark['input_digest'])
        if bound is None or bound['schema_version'] != 2: raise ValueError('Watermark input history missing')
        if role == 'publication':
            fields(watermark['record'], {'observed_at', 'available', 'publisher', 'primary_route', 'recovery_route', 'evidence_ref'}, 'publication watermark')
            instant(watermark['record']['observed_at'])
            if type(watermark['record']['available']) is not bool or watermark['record']['publisher'] != bound['actors']['publication']:
                raise ValueError('Invalid publication watermark binding')
        else:
            validate_registration(watermark['record'], bound, role)
        if watermark['conflict_at'] is not None: instant(watermark['conflict_at'])
    phase = state['phase_evidence']
    fields(phase, {'phase', 'status', 'missing', 'i01_live', 'resume_observation'}, 'phase assessment')
    if (phase['phase'] != value['phase'] or phase['status'] not in {'WAITING', 'PHASE_EVIDENCE_COMPLETE'}
            or phase['i01_live'] not in {'UNVERIFIED', 'OWNER_OBSERVED'} or not isinstance(phase['missing'], list)
            or any(not text(m) for m in phase['missing'])):
        raise ValueError('Invalid phase assessment')
    observation = phase['resume_observation']
    if observation is not None:
        expected = {'schema_version', 'kind', 'dedup_key', 'stage', 'status', 'reason', 'next_owner', 'next_action',
                    'event', 'work', 'receipt', 'action', 'sync', 'recheck', 'matched', 'gate_certified',
                    'deadline_guaranteed', 'waiting_record', 'owner', 'claimed_run_id', 'claimed_started_at',
                    'evidence_history', 'evidence_conflicts', 'input_digest', 'facts_digest', 'attempted_evidence'}
        fields(observation, expected, 'retained owner execution observation')
        if observation['schema_version'] != 1 or observation['kind'] != 'work_owner_resume_observation' or observation['owner'] != value['owner']:
            raise ValueError('Retained execution observation binding differs')
        if any(not isinstance(observation[k], dict) for k in ('evidence_history', 'evidence_conflicts', 'attempted_evidence')):
            raise ValueError('Invalid retained execution history')
        if any(set(observation[k]) - {'event', 'work', 'claim', 'receipt', 'action', 'recheck'} for k in ('evidence_history', 'evidence_conflicts', 'attempted_evidence')):
            raise ValueError('Unknown retained execution history fields')
    for key in ('last_progress_at', 'last_observed_at'):
        if state[key] is not None: instant(state[key])
    if not text(state['next_action']) or not text(state['next_owner']): raise ValueError('Missing next action')
    p.canonical(state)
    return state


def rebase(state, value):
    p.validate_state(state); validate_input(value)
    if state['schema_version'] == 1:
        if value['input_version'] <= state['input']['input_version']:
            raise ValueError('Explicit migration requires a new input version')
        output = new_state(value)
        output['legacy'] = p.rebase(state, legacy_input(value))
        output['input_history'] = copy.deepcopy(state['input_history'] + [state['input']])
        # v1 observation times constrain new observations too; registration
        # evidence must be reacquired, and UNKNOWN legacy operations survive.
        output['next_action'] = 'Contract migrated; rebind owner settings; retained UNKNOWN operations prohibit retransmission'
        return validate_state(output)
    if value == state['input']: return copy.deepcopy(state)
    if (value['input_version'] <= state['input']['input_version']
            or any(value[k] != state['input'][k] for k in ('repository', 'issue', 'purpose', 'owner'))
            or PHASES.index(value['phase']) < PHASES.index(state['input']['phase'])):
        raise ValueError('Old/unrelated input or backward lifecycle transition')
    output = copy.deepcopy(state)
    output['input_history'].append(copy.deepcopy(state['input']))
    output['legacy'] = p.rebase(output['legacy'], legacy_input(value))
    output.update(input=copy.deepcopy(value), input_digest=p.digest(value), status='WAITING',
                  next_action='Input changed; acquire newly bound current evidence')
    output['phase_evidence'] = new_state(value)['phase_evidence']
    output['phase_evidence']['resume_observation'] = copy.deepcopy(state['phase_evidence']['resume_observation'])
    # Never reset registration watermarks or unresolved ledger on digest changes.
    return validate_state(output)


def mark_unknown(state, action):
    validate_state(state)
    if action not in {'review_bind', 'owner_resume'}:
        out = copy.deepcopy(state); out['legacy'] = p.mark_unknown(out['legacy'], action)
        out.update(status='WAITING', next_action='Reconcile legacy UNKNOWN operation; no retransmission')
        return out
    value = state['input']
    if value['pr'] is None: raise ValueError('Real PR required before registration/binding intent')
    key = op_key(value, action)
    if key in state['operations'] or any(o['role'] == action and o['status'] in UNRESOLVED for o in state['operations'].values()):
        raise ValueError('Existing/UNKNOWN/ATTEMPTING operation; reconcile, never recreate')
    out = copy.deepcopy(state)
    out['operations'][key] = dict(role=action, pr=value['pr'], head_sha=value['head_sha'], input_digest=p.digest(value),
                                   status='UNKNOWN', external_id=None, settings_version=None, observed_at=None)
    out.update(status='WAITING', next_action='Reconcile existing registration intent; no retransmission')
    return out


def apply_owner_facts(facts, record, value):
    if record is None: return copy.deepcopy(facts)
    validate_owner_facts(record, value)
    return {**copy.deepcopy(facts), 'owner_record': copy.deepcopy(record)}


def semantic(value):
    """Observation time alone is not progress; retain watermark time separately."""
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k not in {'observed_at', 'last_progress_at', 'last_observed_at'}}
    if isinstance(value, list): return [semantic(v) for v in value]
    return value


def resume(state, facts, observed_at):
    validate_state(state); instant(observed_at)
    value = state['input']
    if facts.get('input_digest') != p.digest(value): raise ValueError('Fresh facts belong to another input')
    output = copy.deepcopy(state)
    record = facts.get('owner_record')
    if record is not None: validate_owner_facts(record, value)
    errors, accepted = [], {}
    # Inspect all roles before rejecting a stale sibling. Newer negative evidence
    # must survive a mixed snapshot or a failed public API collection.
    for role in ROLES:
        current = (record or {}).get(role)
        prior = output['owner_watermarks'].get(role)
        if current is None: continue
        at = instant(current['observed_at'])
        if prior and prior['conflict_at'] and at <= instant(prior['conflict_at']):
            errors.append(role + ': conflicting observation needs a newer readback'); continue
        if prior and at < instant(prior['record']['observed_at']):
            errors.append(role + ': older observation rejected'); continue
        if prior and at == instant(prior['record']['observed_at']) and (current != prior['record'] or prior['input_digest'] != p.digest(value)):
            prior['conflict_at'] = current['observed_at']
            # Retain a negative contradiction as well as the conflict barrier.
            if not ready(current, value, role): prior.update(input_digest=p.digest(value), record=copy.deepcopy(current))
            errors.append(role + ': same-time contradictory observation'); continue
        if prior and current['settings_version'] is not None and prior['record']['settings_version'] is not None and current['settings_version'] < prior['record']['settings_version']:
            errors.append(role + ': older settings revision rejected')
            if ready(current, value, role): continue
        if prior and prior['record']['settings'] != current['settings'] and (
                current['settings_version'] is None or prior['record']['settings_version'] is not None
                and current['settings_version'] <= prior['record']['settings_version']):
            errors.append(role + ': settings change requires newer revision')
            if ready(current, value, role): continue
        negative = not ready(current, value, role, value['phase'] == 'FINISHED')
        if not facts.get('fetch_error') or negative:
            output['owner_watermarks'][role] = dict(input_digest=p.digest(value), record=copy.deepcopy(current), conflict_at=None)
            accepted[role] = current
    legacy_facts = {'input_digest': p.digest(legacy_input(value))}
    if 'legacy_operations' in facts:
        legacy_facts['operations'] = copy.deepcopy(facts['legacy_operations'])
    for key in ('issue', 'main_sha', 'dashboard', 'policy_pr'):
        if key in facts: legacy_facts[key] = copy.deepcopy(facts[key])
    if facts.get('main_policy') == policy_entry(value):
        legacy_facts['main_policy'] = p.policy_entry(legacy_input(value))
    if record is not None:
        publication = {**record['publication'], 'observed_at': record['observed_at']}
        prior_publication = output['owner_watermarks'].get('publication')
        at = instant(record['observed_at'])
        if prior_publication and (at < instant(prior_publication['record']['observed_at'])
                or prior_publication['conflict_at'] and at <= instant(prior_publication['conflict_at'])):
            errors.append('publication: older/conflicting observation rejected')
        elif prior_publication and at == instant(prior_publication['record']['observed_at']) and (publication != prior_publication['record'] or prior_publication['input_digest'] != p.digest(value)):
            prior_publication['conflict_at'] = record['observed_at']
            if not publication['available']: prior_publication.update(input_digest=p.digest(value), record=copy.deepcopy(publication))
            errors.append('publication: same-time contradiction')
        elif not facts.get('fetch_error') or not publication['available']:
            output['owner_watermarks']['publication'] = dict(input_digest=p.digest(value), record=copy.deepcopy(publication), conflict_at=None)
            legacy_facts['publication'] = record['publication']
    # Legacy review event requirements stay intact for v1. v2 uses saved settings
    # at preparation and the real PR event only after a PR exists.
    output['legacy'] = p.resume(output['legacy'], legacy_facts, observed_at)
    missing = list(errors)
    for stage in ('issue', 'policy', 'dashboard', 'publication'):
        if output['legacy']['stages'][stage]['status'] != 'CONFIRMED': missing.append(stage + ': current evidence missing')
    if facts.get('fetch_error'): missing.insert(0, 'Public GitHub facts unavailable; no cached success')
    if value['pr'] is not None:
        pr = facts.get('policy_pr') or {}
        if pr.get('number') != value['pr'] or pr.get('head_sha') != value['head_sha']:
            missing.append('Current public PR/full HEAD binding missing')
    for role in ROLES:
        current = accepted.get(role)
        if role == 'owner_resume' and value['phase'] == 'PRE_IMPLEMENTATION':
            # UNKNOWN intent still blocks, even before this role becomes required.
            if current and current['status'] in UNRESOLVED: missing.insert(0, role + ': reconcile; no retransmission')
            continue
        if current is None or not ready(current, value, role, value['phase'] == 'FINISHED'):
            missing.append(role + ': registration/saved Trigger/Prompt/enabled readback missing or mismatched')
        if role == 'review' and value['phase'] in {'PRE_MERGE', 'POST_MERGE', 'FINISHED'} and (not current or current['event'] is None):
            missing.append('review: actual current PR event not observed')
        if current and value['pr'] is not None:
            action = 'review_bind' if role == 'review' else 'owner_resume'
            key = op_key(value, action)
            previous_op = output['operations'].get(key)
            # A new digest with the same scope/key needs explicit re-binding;
            # old unresolved operations are resolved only by matching real ID.
            if previous_op and previous_op['input_digest'] != p.digest(value) and previous_op['status'] in UNRESOLVED and current['id'] is None:
                missing.insert(0, role + ': old UNKNOWN operation needs real identity reconciliation')
            else:
                output['operations'][key] = dict(role=action, pr=value['pr'], head_sha=value['head_sha'],
                    input_digest=p.digest(value), status=current['status'], external_id=current['id'],
                    settings_version=current['settings_version'], observed_at=current['observed_at'])
    unresolved = any(o['status'] in UNRESOLVED for o in output['operations'].values()) or any(
        o['status'] == 'UNKNOWN' for o in output['legacy']['operations'].values())
    if unresolved: missing.insert(0, 'UNKNOWN/ATTEMPTING ledger: reconcile existing operation; no retransmission')
    waiting = (record or {}).get('waiting_record')
    if value['phase'] in {'PRE_MERGE', 'POST_MERGE', 'FINISHED'}:
        comments = facts.get('issue_comments', [])
        matches = [c for c in comments if waiting and c.get('id') == waiting['comment_id']]
        if (not waiting or len(matches) != 1 or not p.author_matches(matches[0].get('user'), value['owner'])
                or p.hashlib.sha256(matches[0]['body'].encode('utf-8')).hexdigest() != waiting['body_sha256']
                or '<!-- langbench-preparation-' in matches[0]['body'] or '<!-- langbench-automation-state:' in matches[0]['body']):
            missing.append('Independent immutable owner waiting comment/body digest missing')
    prior_observation = state['phase_evidence']['resume_observation']
    observation = None
    live = 'UNVERIFIED'
    if value['phase'] in {'POST_MERGE', 'FINISHED'}:
        execution = (record or {}).get('execution')
        if execution is None:
            missing.append('Actual event/Work start/claim/receipt/sync ZIP/next operation missing')
        else:
            try:
                from tools import work_owner_resume as work_resume
            except ModuleNotFoundError:
                import work_owner_resume as work_resume
            try:
                observation = work_resume.observe(execution, facts.get('resume_facts', {'fetch_error': True}), prior_observation)
            except ValueError:
                observation = prior_observation
                missing.append('Execution scope/history changed; authenticated reconciliation required')
            if observation is None:
                missing.append('Owner execution observation unavailable')
            elif observation['status'] != 'OBSERVED': missing.append('owner execution: ' + observation['reason'])
            elif execution['next_action']['kind'] != 'live_smoke':
                missing.append('safe_stop is observed handling, not an I-01 successful live-smoke cycle')
            else:
                completion = record['completion_observation']
                if (completion is None or completion['dashboard_comment_id'] != (facts.get('dashboard') or {}).get('comment_id')
                        or completion['merge_sha'] != execution['merge_sha']
                        or instant(completion['observed_at']) < instant(execution['next_action']['observed_at'])):
                    missing.append('Owner readback of formal remaining Completion conditions after actual live smoke missing')
                else: live = 'OWNER_OBSERVED'
    if value['phase'] == 'FINISHED' and (record or {}).get('stop') is None:
        missing.append('Dedicated stop operations and disabled=false readback required')
    missing = list(dict.fromkeys(missing))
    output['phase_evidence'] = dict(phase=value['phase'], status='WAITING' if missing else 'PHASE_EVIDENCE_COMPLETE',
                                  missing=missing, i01_live=live, resume_observation=observation or prior_observation)
    output.update(status='WAITING' if missing else 'PHASE_EVIDENCE_COMPLETE', next_owner=value['actors']['dispatch'],
                  next_action=missing[0] if missing else {
                      'PRE_IMPLEMENTATION': 'Begin the authorized implementation',
                      'PR_BOUND': 'Observe the actual review event and prepare the shared waiting record',
                      'PRE_MERGE': 'Combine latest full HEAD CI/independent review/formal Gate for human merge judgment',
                      'POST_MERGE': 'Verify formal Completion limits and stop dedicated registrations',
                      'FINISHED': 'Record completion boundary; do not start another theme'}[value['phase']])
    # Retained clocks are not progress. A new negative/setting/phase is progress;
    # pure timestamp refresh is NO_OP and does not advance progress time.
    if semantic(output) == semantic(state):
        return copy.deepcopy(state)
    output['last_progress_at'] = observed_at; output['last_observed_at'] = observed_at
    return validate_state(output)


def summary(state):
    validate_state(state)
    phase = state['phase_evidence']
    return (f"Issue #{state['input']['issue']} / {state['input']['purpose']} / input v{state['input']['input_version']} / contract v2\n"
            f"Preparation phase: {phase['phase']} / {state['status']}\n"
            + ''.join('- ' + m + '\n' for m in phase['missing'])
            + 'Next owner: ' + state['next_owner'] + '\nNext action: ' + state['next_action'] + '\n'
            + 'PHASE_EVIDENCE_COMPLETE is not formal Merge/Completion PASS. I-01: ' + phase['i01_live'] + '\n'
            + 'Owner UI/tool attestation only; private Work service facts and cross-environment CAS are not certified.\n'
            + '期限保証不能。機械Merge Gate未認定 by this CLI.\n')


def generate(value, config, state=None, owner_facts=None):
    validate_input(value)
    if owner_facts is not None: validate_owner_facts(owner_facts, value)
    state = rebase(state, value) if state else new_state(value)
    request = dict(schema_version=2, kind='startup_preparation_input', repository=value['repository'],
                   issue=value['issue'], purpose=value['purpose'], owner=value['owner'], input_version=value['input_version'],
                   input_digest=p.digest(value), input=value, input_history=state['input_history'], owner_facts=owner_facts,
                   operations={k: {**v, 'status': 'UNKNOWN', 'external_id': None, 'settings_version': None, 'observed_at': None} for k, v in state['operations'].items()},
                   legacy_operations={k: {**v, 'status': 'UNKNOWN', 'external_id': None} for k, v in state['legacy']['operations'].items()})
    return {'issue_body.md': '## 段階別準備 v2\n' + p.canonical(value) + '\n',
            'review_registration.md': (value['registration_prompts']['review'] or {}).get('text') or 'Approved saved review Prompt not yet acquired; preserve existing registration.\n',
            'owner_resume_registration.md': (value['registration_prompts']['owner_resume'] or {}).get('text') or 'PR unconfirmed; owner-resume registration is not required yet.\n',
            'policy_diff.json': p.canonical(p.policy_diff(value, config)) + '\n',
            'preparation.json': p.canonical(state) + '\n', 'summary.md': summary(state),
            'github_record.md': REQUEST_START + p.canonical(request) + p.REQUEST_END + '\n'}
