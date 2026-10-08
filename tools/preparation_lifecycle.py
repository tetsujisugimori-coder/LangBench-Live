"""V3.9 local lifecycle assessment. No Work API, dispatch or formal Gate writes.

Explicit sidecar contract leaves v1 shared records and their meaning unchanged.
Owner identity in local JSON is a binding assertion, not author authentication.
"""
from __future__ import annotations
import copy
from datetime import datetime
try:
    from tools import startup_preparation as p
except ModuleNotFoundError:
    import startup_preparation as p

PHASES = ('PRE_IMPLEMENTATION', 'PRE_MERGE', 'POST_MERGE', 'FINISHED')
FIELDS = {'schema_version', 'input_digest', 'phase', 'pr', 'observed_at',
          'confirmed_by', 'review', 'owner_resume', 'execution'}
REG_FIELDS = {'status', 'id', 'enabled', 'repository', 'issue', 'purpose', 'pr',
              'role', 'trigger', 'condition', 'prompt_digest', 'settings_verified',
              'event_verified', 'evidence_ref'}
STATUSES = {'NOT_ATTEMPTED', 'ATTEMPTING', 'REGISTERED', 'SETTINGS_CONFIRMED',
            'FAILED', 'UNKNOWN', 'DISABLED_CONFIRMED'}
EXEC_FIELDS = {'work_run', 'event_ref', 'handoff_ref', 'claim_at', 'receipt_at',
              'sync_ref', 'artifact_ref', 'action_ref', 'stop_ref'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def instant(value):
    p.timestamp(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate(record, value):
    p.validate_input(value)
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError('Unknown/missing lifecycle fields')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1
            or record['input_digest'] != p.digest(value)
            or record['phase'] not in PHASES
            or record['confirmed_by'] != value['actors']['dispatch']):
        raise ValueError('Lifecycle input/owner/phase binding mismatch')
    observed = instant(record['observed_at'])
    pr = record['pr']
    if pr is not None and (type(pr) is not int or pr <= 0):
        raise ValueError('Invalid lifecycle PR')
    if record['phase'] != 'PRE_IMPLEMENTATION' and pr is None:
        raise ValueError('Actual PR required for this phase')
    for role in ('review', 'owner_resume'):
        r = record[role]
        if not isinstance(r, dict) or set(r) != REG_FIELDS:
            raise ValueError('Unknown/missing registration fields')
        if (r['status'] not in STATUSES or r['role'] != role
                or r['repository'] != value['repository'] or r['issue'] != value['issue']
                or r['purpose'] != value['purpose'] or r['pr'] != pr
                or type(r['settings_verified']) is not bool or type(r['event_verified']) is not bool
                or (r['enabled'] is not None and type(r['enabled']) is not bool)):
            raise ValueError('Registration role/scope/flags mismatch')
        if r['id'] is not None and (not isinstance(r['id'], str)
                or p.re.fullmatch('[a-f0-9]{32}', r['id']) is None):
            raise ValueError('Invalid registration ID')
        if role == 'review' and r['id'] is not None and r['id'] != value['work_automation_id']:
            raise ValueError('Review ID differs from preparation input')
        for key in ('trigger', 'condition', 'evidence_ref'):
            if r[key] is not None and not nonempty(r[key]):
                raise ValueError('Invalid registration evidence')
        if r['prompt_digest'] is not None and (not isinstance(r['prompt_digest'], str)
                or p.re.fullmatch('[a-f0-9]{64}', r['prompt_digest']) is None):
            raise ValueError('Invalid prompt digest')
        if r['status'] in ('REGISTERED', 'SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED'):
            if r['id'] is None or not nonempty(r['evidence_ref']):
                raise ValueError('Registration result lacks ID/evidence')
        if r['settings_verified'] and (r['status'] not in ('SETTINGS_CONFIRMED', 'DISABLED_CONFIRMED')
                or any(r[k] is None for k in ('id', 'enabled', 'trigger', 'condition', 'prompt_digest', 'evidence_ref'))):
            raise ValueError('Settings confirmation lacks saved settings readback')
        if r['status'] == 'DISABLED_CONFIRMED' and (r['enabled'] is not False or not r['settings_verified']):
            raise ValueError('Disabled state must be read back')
        if r['event_verified'] and not nonempty(r['evidence_ref']):
            raise ValueError('Event evidence missing')
    if record['owner_resume']['id'] is not None and record['owner_resume']['id'] == record['review']['id']:
        raise ValueError('Review and owner-resume IDs cannot be shared')
    execution = record['execution']
    if not isinstance(execution, dict) or set(execution) != EXEC_FIELDS:
        raise ValueError('Unknown/missing execution fields')
    for key, item in execution.items():
        if item is not None and not nonempty(item):
            raise ValueError('Invalid execution evidence')
        if key in ('claim_at', 'receipt_at') and item is not None and instant(item) > observed:
            raise ValueError('Execution time is after observation')
    if execution['receipt_at'] is not None and (execution['claim_at'] is None
            or instant(execution['receipt_at']) < instant(execution['claim_at'])):
        raise ValueError('Receipt must follow authenticated shared claim')
    p.canonical(record)
    return record


def ready(r):
    return r['status'] == 'SETTINGS_CONFIRMED' and r['settings_verified'] and r['enabled'] is True


def assess(value, record, previous=None):
    """Rebuild current findings; negative/current evidence never inherits old success.

    previous must be the saved local assessment. History is never formal proof.
    """
    validate(record, value)
    history = []
    if previous is not None:
        if (not isinstance(previous, dict) or set(previous) != {'schema_version', 'input_digest',
                'record', 'history', 'status', 'missing', 'next_owner', 'next_action', 'formal_gate'}
                or previous['schema_version'] != 1 or previous['formal_gate'] != 'NOT_CERTIFIED'
                or not isinstance(previous['history'], list)):
            raise ValueError('Broken lifecycle assessment')
        # Input changes need explicit re-binding; retained sidecar is never silently migrated.
        if previous['input_digest'] != p.digest(value):
            raise ValueError('Lifecycle input changed; preserve old report and re-bind a new sidecar')
        for old in previous['history'] + [previous['record']]:
            validate(old, value)
        if instant(record['observed_at']) < instant(previous['record']['observed_at']):
            raise ValueError('Older lifecycle observation cannot restore success')
        if record['observed_at'] == previous['record']['observed_at'] and record != previous['record']:
            raise ValueError('Conflicting observations at same time')
        if PHASES.index(record['phase']) < PHASES.index(previous['record']['phase']):
            raise ValueError('Lifecycle phase cannot move backwards')
        history = copy.deepcopy(previous['history'])
        if record != previous['record']:
            history.append(copy.deepcopy(previous['record']))
    phase = record['phase']
    missing = []
    review, owner = record['review'], record['owner_resume']
    # Any unresolved attempt prevents sending another request, even at an earlier phase.
    for role in ('review', 'owner_resume'):
        if record[role]['status'] in ('UNKNOWN', 'ATTEMPTING'):
            missing.append(role + ': reconcile existing attempt; no retransmission')
    if not ready(review) and not (phase == 'FINISHED' and review['status'] == 'DISABLED_CONFIRMED'):
        missing.append('review: registration and saved settings readback')
    if phase != 'PRE_IMPLEMENTATION':
        if not review['event_verified']:
            missing.append('review: actual PR event evidence')
        if not ready(owner) and not (phase == 'FINISHED' and owner['status'] == 'DISABLED_CONFIRMED'):
            missing.append('owner_resume: merge registration and saved settings readback')
        if owner['trigger'] != 'pull_request_merged':
            missing.append('owner_resume: normalized merged-only trigger (closed must enforce merged condition)')
        if not nonempty(record['execution']['handoff_ref']):
            missing.append('execution: shared handoff record')
    if phase in ('POST_MERGE', 'FINISHED'):
        if not owner['event_verified']:
            missing.append('owner_resume: actual merge event evidence')
        for key in EXEC_FIELDS - {'stop_ref'}:
            if record['execution'][key] is None:
                missing.append('execution: ' + key)
    if phase == 'FINISHED':
        if any(record[r]['status'] != 'DISABLED_CONFIRMED' for r in ('review', 'owner_resume')):
            missing.append('stop: dedicated registrations disabled readback')
        if record['execution']['stop_ref'] is None:
            missing.append('stop: evidence')
    return {'schema_version': 1, 'input_digest': p.digest(value), 'record': copy.deepcopy(record),
            'history': history, 'status': 'WAITING' if missing else 'PHASE_EVIDENCE_COMPLETE',
            'missing': missing, 'next_owner': value['actors']['dispatch'],
            'next_action': missing[0] if missing else {
                'PRE_IMPLEMENTATION': 'Verify legacy Issue/policy/Dashboard/publication readiness; then implementation',
                'PRE_MERGE': 'Root must combine latest CI, independent review and formal Gate before merge recommendation',
                'POST_MERGE': 'Root must verify formal completion and stop dedicated monitoring',
                'FINISHED': 'Record handoff and completion boundaries'}[phase],
            'formal_gate': 'NOT_CERTIFIED'}


def summary(report):
    return ('Lifecycle: ' + report['record']['phase'] + ' / ' + report['status'] + '\n'
            + '\n'.join('- ' + m for m in report['missing']) + '\n'
            + 'Next owner: ' + report['next_owner'] + '\nNext action: ' + report['next_action'] + '\n'
            + 'Local owner assertions only. Formal Merge/Completion Gate: NOT_CERTIFIED.\n')
