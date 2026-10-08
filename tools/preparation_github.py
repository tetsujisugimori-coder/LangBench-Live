"""Public GitHub preparation transport. Writes are called ONLY by trusted main.

Separate owner input and writer snapshot markers; no Gate state mutation.
Comment PATCH lacks CAS: serialize in existing workflow, double-read before and
verify after write. Ambiguous writes raise and are never automatically retried.
"""
from __future__ import annotations
import zipfile
import base64
import copy
import re
try:
    from tools import startup_preparation as preparation
    from tools.automation_dashboard import author_matches, BOT, RECEIPT, envelope, parse_state, REPOSITORY
except ModuleNotFoundError:
    import startup_preparation as preparation
    from automation_dashboard import author_matches, BOT, RECEIPT, envelope, parse_state, REPOSITORY


class PreparationConflict(ValueError):
    pass


class PreparationWriteUnknown(ValueError):
    pass


def validate_owner_facts(record, value):
    """Validate explicit Work/publication observations supplied by the formal owner.

    This is deliberately an input contract, not a private Work API adapter.
    """
    if value.get('schema_version') == 2:
        return preparation.evidence_contract().validate_owner_facts(record, value)
    fields = {'schema_version', 'repository', 'issue', 'purpose', 'owner', 'input_version',
              'input_digest', 'start_main_sha', 'observed_at', 'review', 'publication'}
    if not isinstance(record, dict) or set(record) != fields:
        raise PreparationConflict('Owner observation schema invalid')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1 or record['repository'] != value['repository']
            or type(record['issue']) is not type(value['issue']) or record['issue'] != value['issue'] or record['purpose'] != value['purpose']
            or record['owner'] != value['owner'] or type(record['input_version']) is not int or record['input_version'] != value['input_version']
            or record['input_digest'] != preparation.digest(value)
            or record['start_main_sha'] != value['start_main_sha']):
        raise PreparationConflict('Owner observation scope/input/SHA binding failed')
    preparation.timestamp(record['observed_at'])
    review = record['review']
    review_fields = {'available', 'id', 'enabled', 'target_event', 'actual_event',
                     'event_verified', 'evidence_ref', 'confirmed_by'}
    if (not isinstance(review, dict) or set(review) != review_fields
            or type(review['available']) is not bool or review['confirmed_by'] != value['actors']['dispatch']
            or not isinstance(review['evidence_ref'], str) or not review['evidence_ref']):
        raise PreparationConflict('Owner review observation invalid')
    if review['available']:
        if (value['work_automation_id'] is None or review['id'] != value['work_automation_id'] or type(review['enabled']) is not bool
                or type(review['event_verified']) is not bool
                or not isinstance(review['target_event'], str) or not review['target_event']
                or (review['event_verified'] and (not isinstance(review['actual_event'], str) or not review['actual_event']))
                or (not review['event_verified'] and review['actual_event'] is not None
                    and (not isinstance(review['actual_event'], str) or not review['actual_event']))):
            raise PreparationConflict('Owner review result invalid')
    elif any(review[k] is not None for k in ('id', 'enabled', 'target_event', 'actual_event', 'event_verified')):
        raise PreparationConflict('Unavailable review cannot claim a result')
    publication = record['publication']
    publication_fields = {'available', 'publisher', 'primary_route', 'recovery_route', 'evidence_ref'}
    if (not isinstance(publication, dict) or set(publication) != publication_fields
            or type(publication['available']) is not bool
            or publication['publisher'] != value['actors']['publication']
            or not isinstance(publication['evidence_ref'], str) or not publication['evidence_ref']):
        raise PreparationConflict('Owner publication observation invalid')
    routes = ('primary_route', 'recovery_route')
    if publication['available'] and any(not isinstance(publication[k], str) or not publication[k] for k in routes):
        raise PreparationConflict('Confirmed publication routes missing')
    if not publication['available'] and any(publication[k] is not None for k in routes):
        raise PreparationConflict('Unavailable publication cannot claim routes')
    return record


def apply_owner_facts(facts, record, value):
    """Bind explicit owner observations before both CLI and writer resumes."""
    if value.get('schema_version') == 2:
        return preparation.evidence_contract().apply_owner_facts(facts, record, value)
    if record is None:
        return facts
    validate_owner_facts(record, value)
    output = copy.deepcopy(facts)
    for stage in ('review', 'publication'):
        output[stage] = {**copy.deepcopy(record[stage]), 'owner_observed_at': record['observed_at']}
    return output


def block(body, start, end):
    if start not in body and end not in body: return None
    if body.count(start) != 1 or body.count(end) != 1:
        raise PreparationConflict('Malformed/ambiguous preparation marker')
    a = body.index(start); b = body.index(end)
    if b <= a: raise PreparationConflict('Malformed preparation marker ordering')
    return preparation.loads(body[a + len(start):b])


def read_facts(api, value):
    """Read current Issue, linked configuration PR, exact main contents and Dashboard.

    No Work API: registration/real events remain explicitly unconfirmed.
    No failure turns into a missing/successful fact; exceptions propagate.
    """
    preparation.validate_input(value)
    facts = {'input_digest': preparation.digest(value)}
    if value['issue'] is not None:
        issue = api.get(f"/issues/{value['issue']}")
        if 'pull_request' in issue or issue.get('number') != value['issue']:
            raise PreparationConflict('Issue identity unavailable')
        if not re.search(r'(?m)^purpose:\s*' + re.escape(value['purpose']) + r'\s*$', issue.get('body', '')):
            raise PreparationConflict('Issue purpose mismatch')
        if not author_matches(issue.get('user'), value['owner']):
            raise PreparationConflict('Issue formal owner mismatch')
        facts['issue'] = {'number': issue['number'], 'repository': REPOSITORY, 'purpose': value['purpose'],
                          'owner': issue['user'], 'url': issue.get('html_url')}
    ref = api.get('/git/ref/heads/main')
    head = ref.get('object', {}).get('sha')
    if not preparation.sha(head): raise PreparationConflict('Main SHA unavailable')
    file = api.get('/contents/.github/automation-dashboard.json?ref=' + head)
    if file.get('encoding') != 'base64': raise PreparationConflict('Policy encoding unavailable')
    config = preparation.loads(base64.b64decode(file['content'], validate=False).decode('utf-8'))
    try:
        from tools.automation_dashboard import validate_policy_config
    except ModuleNotFoundError:
        from automation_dashboard import validate_policy_config
    validate_policy_config(config)
    facts['main_sha'] = head
    if value['issue'] is None: return facts
    policy = config['issues'].get(str(value['issue']))
    if policy is not None: facts['main_policy'] = policy
    pulls = api.pages('/pulls?state=all&sort=updated&direction=desc')
    matching = [p for p in pulls if re.search(rf'(?m)^Refs #{value["issue"]}\s*$', p.get('body') or '')
                and p.get('base', {}).get('ref') == 'main'
                and p.get('base', {}).get('repo', {}).get('full_name') == REPOSITORY]
    if len(matching) > 1: raise PreparationConflict('Multiple matching PRs; no automatic binding')
    if matching:
        pull = api.get(f'/pulls/{matching[0]["number"]}')
        if not preparation.sha(pull.get('head', {}).get('sha')):
            raise PreparationConflict('PR head unavailable')
        facts['policy_pr'] = {'number': pull['number'], 'merged': pull.get('merged') is True,
                              'head_sha': pull['head']['sha'], 'url': pull.get('html_url')}
    comments = api.pages(f"/issues/{value['issue']}/comments")
    if policy:
        try:
            from tools.update_automation_dashboard import select_dashboard
        except ModuleNotFoundError:
            from update_automation_dashboard import select_dashboard
        dashboard = select_dashboard(comments, policy)
        if dashboard:
            parsed = parse_state(dashboard['body'], value['issue'], policy)
            if parsed is not None:
                facts['dashboard'] = {'repository': parsed['repository'], 'issue': parsed['issue'],
                    'purpose': parsed['purpose'], 'comment_id': dashboard['id']}
    if value['schema_version'] == 2:
        facts['issue_comments'] = [c for c in comments if request_version(c.get('body', '')) is None]
    # No dispatch state is transformed into preparation or Gate PASS.
    return facts


def authenticated_request(comment, issue, policy):
    body = comment.get('body', '')
    version = request_version(body)
    if version == 2:
        return authenticated_request_v2(comment, issue, policy)
    if policy.get('preparation_contract') == 2 and version == 1:
        raise PreparationConflict('Policy requires v2; explicit input migration required')
    record = block(body, preparation.REQUEST_START, preparation.REQUEST_END)
    if record is None: return None
    if not author_matches(comment.get('user'), policy['owner']):
        raise PreparationConflict('Preparation record author is not formal owner')
    fields = {'schema_version', 'kind', 'repository', 'issue', 'purpose', 'owner',
              'input_version', 'input_digest', 'input', 'input_history', 'owner_facts', 'operations'}
    if not isinstance(record, dict) or set(record) != fields:
        raise PreparationConflict('Preparation request schema invalid')
    value = preparation.validate_input(record['input'])
    if (type(record['schema_version']) is not int or record['schema_version'] != 1
            or record['kind'] != 'startup_preparation_input' or record['repository'] != REPOSITORY
            or type(record['issue']) is not int or record['issue'] != issue or value['issue'] != issue
            or record['purpose'] != policy['purpose'] or value['purpose'] != policy['purpose']
            or record['owner'] != policy['owner'] or value['owner'] != policy['owner']
            or type(record['input_version']) is not int or record['input_version'] != value['input_version'] or record['input_digest'] != preparation.digest(value)
            or preparation.policy_entry(value) != policy):
        raise PreparationConflict('Preparation scope/owner/input/policy authentication failed')
    candidate = preparation.new_state(value)
    candidate['input_history'] = record['input_history']
    candidate['operations'] = record['operations']
    preparation.validate_state(candidate)
    if any(v['status'] != 'UNKNOWN' or v['external_id'] is not None for v in record['operations'].values()):
        raise PreparationConflict('Request cannot claim external operation success')
    if record['owner_facts'] is not None:
        validate_owner_facts(record['owner_facts'], value)
    return record


def snapshot(body):
    if 'langbench-preparation-snapshot:v2' in body:
        return snapshot_v2(body)
    value = block(body, preparation.SNAPSHOT_START, preparation.SNAPSHOT_END)
    if value is None: return None
    fields = {'schema_version', 'kind', 'comment_id', 'input_version', 'input_digest', 'state', 'source_digest'}
    if not isinstance(value, dict) or set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != 'startup_preparation_snapshot':
        raise PreparationConflict('Snapshot schema invalid')
    if type(value['comment_id']) is not int or value['comment_id'] <= 0 or not isinstance(value['source_digest'], str) or re.fullmatch('[0-9a-f]{64}', value['source_digest']) is None:
        raise PreparationConflict('Snapshot identity/source digest invalid')
    state = preparation.validate_state(value['state'])
    if value['input_version'] != state['input']['input_version'] or value['input_digest'] != state['input_digest']:
        raise PreparationConflict('Snapshot input binding invalid')
    return value


def reconcile_operations(api, issue, policy, state, facts):
    resolved = {}
    comments = api.pages(f'/issues/{issue}/comments')
    for key, operation in state['operations'].items():
        current = state['input']
        # Old input operations cannot be guessed against new identities.
        if operation['input_digest'] != state['input_digest']: continue
        if key == preparation.operation_key(current, 'issue'):
            resolved[key] = {'id': issue, 'input_digest': operation['input_digest']}
        elif key == preparation.operation_key(current, 'policy_pr') and facts.get('policy_pr'):
            resolved[key] = {'id': facts['policy_pr']['number'], 'input_digest': operation['input_digest']}
        elif key in {preparation.operation_key(current, a) for a in ('implementation_task', 'fix_task')}:
            receipts = []
            for comment in comments:
                record = envelope(comment.get('body'), RECEIPT)
                if not record or not author_matches(comment.get('user'), policy['owner']): continue
                if record.get('repository') != REPOSITORY or record.get('issue') != issue: continue
                receipt = record.get('dispatch', {})
                try:
                    from tools.automation_dashboard import valid_receipt
                except ModuleNotFoundError:
                    from automation_dashboard import valid_receipt
                if valid_receipt(issue, policy, receipt) and receipt['dedup_key'] == key:
                    receipts.append(receipt['run_id'])
            identities = set(receipts)
            if len(identities) > 1: raise PreparationConflict('Duplicate dispatch; owner reconciliation required')
            if identities: resolved[key] = {'id': identities.pop(), 'input_digest': operation['input_digest']}
    return resolved


VIEW_START = '<!-- langbench-preparation-view:start -->'
VIEW_END = '<!-- langbench-preparation-view:end -->'


def replace_snapshot(body, content):
    # Only writer-owned snapshot changes. Input and all human prose are byte-preserved.
    if VIEW_START in body or VIEW_END in body:
        if body.count(VIEW_START) != 1 or body.count(VIEW_END) != 1 or body.index(VIEW_END) <= body.index(VIEW_START):
            raise PreparationConflict('Malformed preparation view region')
        start = body.index(VIEW_START); end = body.index(VIEW_END) + len(VIEW_END)
        snapshot(body[start:end])
        return body[:start] + content + body[end:]
    if 'langbench-preparation-snapshot:' in body:
        snapshot(body)
        start = body.index('<!-- langbench-preparation-snapshot:')
        end = body.index(preparation.SNAPSHOT_END) + len(preparation.SNAPSHOT_END)
        return body[:start] + content + body[end:]
    return body + '\n\n' + content


def authenticate_comment(comment, issue, policy, expected_id=None):
    """Validate the REST target and owner record independently of metadata."""
    if (not isinstance(comment, dict) or type(comment.get('id')) is not int
            or comment['id'] <= 0 or (expected_id is not None and comment['id'] != expected_id)
            or comment.get('issue_url') != f'https://api.github.com/repos/{REPOSITORY}/issues/{issue}'
            or not isinstance(comment.get('body'), str)):
        raise PreparationConflict('Preparation comment identity/body unavailable or mismatched')
    user = comment.get('user')
    if (not isinstance(user, dict) or type(user.get('id')) is not int or user['id'] <= 0
            or not isinstance(user.get('login'), str) or not isinstance(user.get('type'), str)):
        raise PreparationConflict('Preparation comment author identity unavailable')
    preparation.timestamp(comment.get('updated_at'))
    record = authenticated_request(comment, issue, policy)
    if record is None:
        raise PreparationConflict('Preparation request missing from same comment')
    saved = snapshot(comment['body'])
    if saved is not None:
        if saved['comment_id'] != comment['id']:
            raise PreparationConflict('Snapshot comment identity mismatch')
        if saved['schema_version'] != record['schema_version'] and not (
                saved['schema_version'] == 1 and record['schema_version'] == 2
                and saved['state']['input'] in record['input_history']):
            raise PreparationConflict('Mixed snapshot/request contract without explicit migration')
    return record


def reconcile_preparation(api, issue, policy, now):
    if policy.get('preparation_contract') == 2:
        return reconcile_preparation_v2(api, issue, policy, now)
    if type(issue) is not int or issue <= 0: raise PreparationConflict('Formal Issue ID unavailable')
    comments = api.pages(f'/issues/{issue}/comments')
    if any(not isinstance(c, dict) or not isinstance(c.get('body'), str) for c in comments):
        raise PreparationConflict('Comment list body unavailable; cannot select preparation record')
    candidates = [c for c in comments if request_version(c.get('body', '')) is not None]
    if not candidates: return 'NO_RECORD'
    if len(candidates) != 1: raise PreparationConflict('Multiple preparation records; do not create another')
    comment = candidates[0]
    record = authenticate_comment(comment, issue, policy)
    prior = snapshot(comment['body'])
    value = record['input']
    if prior:
        if prior['comment_id'] != comment['id']: raise PreparationConflict('Snapshot comment identity mismatch')
        state = prior['state']
        prefix = state['input_history'] + ([] if value == state['input'] else [state['input']])
        if record['input_history'][:len(prefix)] != prefix or (value == state['input'] and record['input_history'] != prefix):
            raise PreparationConflict('Owner input transition history differs from saved history')
        for intermediate in record['input_history'][len(prefix):] + [value]:
            state = preparation.rebase(state, intermediate)
        if record['input_history'] != state['input_history']:
            raise PreparationConflict('Owner input transition history differs from saved history')
        if any(operation['status'] == 'UNKNOWN' and key not in record['operations']
               for key, operation in state['operations'].items()):
            raise PreparationConflict('Owner request removed unresolved operation history')
    else:
        state = preparation.new_state(value)
        state['input_history'] = copy.deepcopy(record['input_history'])
    for key, operation in record['operations'].items():
        existing = state['operations'].get(key)
        if existing is not None and existing['input_digest'] != operation['input_digest']:
            raise PreparationConflict('Operation input binding changed; reconcile instead of resend')
        if existing is None:
            history = state['input_history'] + [value]
            if not any(operation['input_digest'] == preparation.digest(bound)
                       and key in {preparation.operation_key(bound, action) for action in preparation.ACTIONS}
                       for bound in history):
                raise PreparationConflict('New operation scope differs from input')
            state['operations'][key] = copy.deepcopy(operation)
    first = apply_owner_facts(read_facts(api, value), record['owner_facts'], value)
    first['operations'] = reconcile_operations(api, issue, policy, state, first)
    second = apply_owner_facts(read_facts(api, value), record['owner_facts'], value)
    second['operations'] = reconcile_operations(api, issue, policy, state, second)
    latest = api.get(f'/issues/comments/{comment["id"]}')
    authenticate_comment(latest, issue, policy, comment['id'])
    if first != second or latest['body'] != comment['body']:
        raise PreparationConflict('Concurrent preparation edit/fact change; no write')
    # An update timestamp is an auxiliary edit signal, not a body fingerprint.
    # Even if an edit restored identical text, require a fresh reconciliation.
    if latest['updated_at'] != comment['updated_at']:
        raise PreparationConflict('Comment update information changed; fresh read required; no write')
    updated = preparation.resume(state, second, now)
    updated['shared_persistence'] = True
    # Request changes and human-only edits have distinct source fingerprints.
    source_digest = preparation.digest(record)
    saved = {'schema_version': 1, 'kind': 'startup_preparation_snapshot', 'comment_id': comment['id'],
             'input_version': value['input_version'], 'input_digest': preparation.digest(value),
             'state': updated, 'source_digest': source_digest}
    if prior == saved: return 'NO_OP'
    content = (VIEW_START + '\n## 開始準備の現在要約\n\n'
               + '\n'.join('    ' + line for line in preparation.summary(updated).splitlines())
               + '\n\n' + preparation.SNAPSHOT_START + preparation.canonical(saved)
               + preparation.SNAPSHOT_END + '\n' + VIEW_END)
    body = replace_snapshot(latest['body'], content)
    if len(body.encode()) > 60000: raise PreparationConflict('Preparation comment exceeds bound')
    # There is no resend loop: transport errors may have committed remotely.
    try:
        written = api.request(api.root + f'/issues/comments/{comment["id"]}', 'PATCH', {'body': body})
        checked = api.get(f'/issues/comments/{comment["id"]}')
        authenticate_comment(written, issue, policy, comment['id'])
        authenticate_comment(checked, issue, policy, comment['id'])
        after = apply_owner_facts(read_facts(api, value), record['owner_facts'], value)
        after['operations'] = reconcile_operations(api, issue, policy, updated, after)
    except Exception as exc:
        raise PreparationWriteUnknown('Preparation write outcome unknown; inspect same comment before retry') from exc
    if written['body'] != body or checked['body'] != body or after != second:
        raise PreparationWriteUnknown('Post-write conflict; stored snapshot is not certified; fresh read required')
    return 'UPDATED'


def request_version(body):
    """Never silently ignore unknown/mixed preparation contracts."""
    versions = re.findall(r'<!-- langbench-preparation-input:([^\s]+)', body)
    snapshots = re.findall(r'<!-- langbench-preparation-snapshot:([^\s]+)', body)
    if len(versions) > 1 or len(snapshots) > 1 or any(v not in {'v1', 'v2'} for v in versions + snapshots):
        raise PreparationConflict('Unknown/mixed preparation marker versions')
    if not versions:
        if preparation.REQUEST_END in body: raise PreparationConflict('Preparation end without start')
        return None
    return int(versions[0][1:])


def authenticated_request_v2(comment, issue, policy):
    contract = preparation.evidence_contract()
    if type(policy.get('preparation_contract')) is not int or policy['preparation_contract'] != 2:
        raise PreparationConflict('Reader/policy does not support v2 input')
    if not author_matches(comment.get('user'), policy['owner']):
        raise PreparationConflict('Preparation record author is not formal owner')
    record = block(comment['body'], contract.REQUEST_START, preparation.REQUEST_END)
    fields = {'schema_version', 'kind', 'repository', 'issue', 'purpose', 'owner', 'input_version',
              'input_digest', 'input', 'input_history', 'owner_facts', 'operations', 'legacy_operations'}
    contract.fields(record, fields, 'v2 request')
    value = preparation.validate_input(record['input'])
    if (type(record['schema_version']) is not int or record['schema_version'] != 2 or value['schema_version'] != 2
            or record['kind'] != 'startup_preparation_input' or record['issue'] != issue
            or type(record['issue']) is not int or value['issue'] != issue
            or any(record[k] != value[k] or type(record[k]) is not type(value[k])
                   for k in ('repository', 'purpose', 'owner', 'input_version'))
            or record['input_digest'] != preparation.digest(value) or contract.policy_entry(value) != policy):
        raise PreparationConflict('v2 author/policy/scope/input binding failed')
    candidate = contract.new_state(value)
    candidate['input_history'] = copy.deepcopy(record['input_history'])
    candidate['operations'] = copy.deepcopy(record['operations'])
    candidate['legacy']['input_history'] = [contract.legacy_input(v) if v['schema_version'] == 2 else v for v in record['input_history']]
    candidate['legacy']['operations'] = copy.deepcopy(record['legacy_operations'])
    contract.validate_state(candidate)
    if any(o['status'] not in {'NOT_ATTEMPTED', 'ATTEMPTING', 'UNKNOWN'} or o['external_id'] is not None
           for o in record['operations'].values()) or any(o['status'] != 'UNKNOWN' or o['external_id'] is not None
           for o in record['legacy_operations'].values()):
        raise PreparationConflict('Owner intents cannot claim operation success without readback')
    if record['owner_facts'] is not None: contract.validate_owner_facts(record['owner_facts'], value)
    return record


def snapshot_v2(body):
    contract = preparation.evidence_contract()
    if body.count('<!-- langbench-preparation-snapshot:') != 1:
        raise PreparationConflict('Mixed snapshot versions')
    saved = block(body, contract.SNAPSHOT_START, preparation.SNAPSHOT_END)
    contract.fields(saved, {'schema_version', 'kind', 'comment_id', 'input_version', 'input_digest', 'state', 'source_digest'}, 'v2 snapshot')
    if (type(saved['schema_version']) is not int or saved['schema_version'] != 2
            or saved['kind'] != 'startup_preparation_snapshot' or not contract.positive(saved['comment_id'])
            or not isinstance(saved['source_digest'], str) or not re.fullmatch('[a-f0-9]{64}', saved['source_digest'])):
        raise PreparationConflict('Invalid snapshot identity/version')
    state = contract.validate_state(saved['state'])
    if saved['input_version'] != state['input']['input_version'] or saved['input_digest'] != state['input_digest']:
        raise PreparationConflict('Mixed snapshot input binding')
    return saved


def state_for_request(record, prior):
    """Explicit migration uses the immutable input prefix; never copy cached PASS."""
    contract = preparation.evidence_contract()
    value = record['input']
    if prior:
        state = prior['state']
        prefix = state['input_history'] + ([] if value == state['input'] else [state['input']])
        if record['input_history'][:len(prefix)] != prefix or (value == state['input'] and record['input_history'] != prefix):
            raise PreparationConflict('Input transition history changed')
        for intermediate in record['input_history'][len(prefix):] + [value]:
            state = preparation.rebase(state, intermediate)
        if state['input_history'] != record['input_history']: raise PreparationConflict('Input migration prefix differs')
    else:
        state = contract.new_state(value)
        state['input_history'] = copy.deepcopy(record['input_history'])
        state['legacy']['input_history'] = [contract.legacy_input(v) if v['schema_version'] == 2 else v for v in record['input_history']]
    out = copy.deepcopy(state)
    for field, target in (('operations', out['operations']), ('legacy_operations', out['legacy']['operations'])):
        requested = record[field]
        if any(o['status'] in {'UNKNOWN', 'ATTEMPTING'} and k not in requested for k, o in target.items()):
            raise PreparationConflict('Unresolved ledger was removed')
        for key, operation in requested.items():
            existing = target.get(key)
            if existing and existing['input_digest'] != operation['input_digest']:
                raise PreparationConflict('Operation binding changed without authenticated reconciliation')
            if existing is None: target[key] = copy.deepcopy(operation)
    return contract.validate_state(out)


def select_preparation(comments, issue, policy):
    if any(not isinstance(c, dict) or not isinstance(c.get('body'), str) for c in comments):
        raise PreparationConflict('Comment bodies unavailable')
    candidates = [c for c in comments if request_version(c['body']) is not None]
    if len(candidates) != 1: raise PreparationConflict('Exactly one current formal preparation record required')
    comment = candidates[0]
    record = authenticate_comment(comment, issue, policy)
    if record['schema_version'] != 2: raise PreparationConflict('Explicit v2 migration required')
    return comment, record, snapshot(comment['body'])


def authenticated_cli_record(api, value, local_owner, local_state):
    """Formal REST comment identity, trusted main policy, exact local proposal.

    Saved local state contributes only prohibitions, never positive authority.
    """
    contract = preparation.evidence_contract()
    head = api.get('/git/ref/heads/main')['object']['sha']
    if not preparation.sha(head): raise PreparationConflict('Main SHA unavailable')
    file = api.get('/contents/.github/automation-dashboard.json?ref=' + head)
    if file.get('encoding') != 'base64': raise PreparationConflict('Policy encoding unavailable')
    config = preparation.loads(base64.b64decode(file['content']).decode('utf-8'))
    try:
        from tools.automation_dashboard import validate_policy_config
    except ModuleNotFoundError:
        from automation_dashboard import validate_policy_config
    validate_policy_config(config)
    policy = config['issues'].get(str(value['issue']))
    if policy != preparation.policy_entry(value): raise PreparationConflict('Current main policy binding mismatch')
    issue = api.get(f'/issues/{value["issue"]}')
    if (issue.get('number') != value['issue'] or 'pull_request' in issue
            or not author_matches(issue.get('user'), value['owner'])
            or not re.search(r'(?m)^purpose:\s*' + re.escape(value['purpose']) + r'\s*$', issue.get('body', ''))):
        raise PreparationConflict('Formal Issue identity/purpose mismatch')
    comment, record, prior = select_preparation(api.pages(f'/issues/{value["issue"]}/comments'), value['issue'], policy)
    if record['input'] != value or (local_owner is not None and local_owner != record['owner_facts']):
        raise PreparationConflict('Local input/owner facts differ from authenticated shared input')
    state = state_for_request(record, prior)
    if local_state['input_history'] != state['input_history']:
        raise PreparationConflict('Local/shared input history mismatch')
    for role, watermark in local_state['owner_watermarks'].items():
        bound = next((v for v in [value] + local_state['input_history'] if preparation.digest(v) == watermark['input_digest']), None)
        negative = not watermark['record']['available'] if role == 'publication' else not contract.ready(watermark['record'], bound, role, bound['phase'] == 'FINISHED')
        if not negative and watermark['conflict_at'] is None: continue
        existing = state['owner_watermarks'].get(role)
        if existing is None or max(contract.instant(watermark['record']['observed_at']), contract.instant(watermark['conflict_at'] or watermark['record']['observed_at'])) >= contract.instant(existing['record']['observed_at']):
            state['owner_watermarks'][role] = copy.deepcopy(watermark)
    for target, source in ((state['operations'], local_state['operations']), (state['legacy']['operations'], local_state['legacy']['operations'])):
        for key, operation in source.items():
            if operation['status'] in {'UNKNOWN', 'ATTEMPTING'}:
                if key in target and target[key]['input_digest'] != operation['input_digest']:
                    raise PreparationConflict('Local unresolved operation binding mismatch')
                target[key] = copy.deepcopy(operation)
    contract.validate_state(state)
    return record, state, comment


def current_preparation_facts(api, value, record, state=None):
    """Fresh public facts plus authenticated owner attestation; no private API."""
    facts = apply_owner_facts(read_facts(api, value), record['owner_facts'], value)
    if state is not None:
        legacy = state['legacy']
        legacy_facts = {**facts, 'input_digest': legacy['input_digest']}
        facts['legacy_operations'] = reconcile_operations(api, value['issue'], preparation.policy_entry(legacy['input']), legacy, legacy_facts)
    execution = (record['owner_facts'] or {}).get('execution')
    if execution is not None:
        try:
            from tools import work_owner_resume as resume
        except ModuleNotFoundError:
            import work_owner_resume as resume
        facts['resume_facts'] = resume.read_facts(api, execution)
        facts['resume_facts']['issue_comments'] = [c for c in facts['resume_facts']['issue_comments'] if request_version(c.get('body', '')) is None]
    return facts


def preserve_negative_failure(state, record, now):
    """No API success: retain only bound negative role observations, fail closed."""
    facts = {'input_digest': state['input_digest'], 'fetch_error': True}
    facts = apply_owner_facts(facts, record['owner_facts'], state['input'])
    return preparation.resume(state, facts, now)


def reconcile_preparation_v2(api, issue, policy, now):
    contract = preparation.evidence_contract()
    comments = api.pages(f'/issues/{issue}/comments')
    comment, record, prior = select_preparation(comments, issue, policy)
    state = state_for_request(record, prior)
    value = record['input']
    failure = False
    try:
        first = current_preparation_facts(api, value, record, state)
        second = current_preparation_facts(api, value, record, state)
        if first != second: raise PreparationConflict('Concurrent public fact change')
        updated = preparation.resume(state, second, now)
    except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile):
        # A safe negative snapshot can still be persisted if the same owner
        # comment can be authenticated; no positive evidence is certified.
        updated = preserve_negative_failure(state, record, now)
        failure = True
        second = None
    latest = api.get(f'/issues/comments/{comment["id"]}')
    authenticate_comment(latest, issue, policy, comment['id'])
    if latest['body'] != comment['body'] or latest['updated_at'] != comment['updated_at']:
        raise PreparationConflict('Concurrent comment edit; no write')
    updated['shared_persistence'] = True
    saved = dict(schema_version=2, kind='startup_preparation_snapshot', comment_id=comment['id'],
                 input_version=value['input_version'], input_digest=preparation.digest(value),
                 state=updated, source_digest=preparation.digest(contract.semantic(record)))
    if prior == saved:
        if failure: raise PreparationConflict('Public facts unavailable; retained negative history')
        return 'NO_OP'
    content = (VIEW_START + '\n## 段階別準備の現在要約\n\n'
               + '\n'.join('    ' + line for line in preparation.summary(updated).splitlines())
               + '\n\n' + contract.SNAPSHOT_START + preparation.canonical(saved)
               + preparation.SNAPSHOT_END + '\n' + VIEW_END)
    body = replace_snapshot(latest['body'], content)
    if len(body.encode('utf-8')) > 60000: raise PreparationConflict('Comment exceeds safe bound')
    try:
        written = api.request(api.root + f'/issues/comments/{comment["id"]}', 'PATCH', {'body': body})
        checked = api.get(f'/issues/comments/{comment["id"]}')
        authenticate_comment(written, issue, policy, comment['id'])
        authenticate_comment(checked, issue, policy, comment['id'])
        if written['body'] != body or checked['body'] != body:
            raise PreparationConflict('Post-write comment conflict')
        if not failure and current_preparation_facts(api, value, record, state) != second:
            raise PreparationConflict('Post-write public facts changed')
    except Exception as exc:
        raise PreparationWriteUnknown('Write result UNKNOWN; reconcile same comment, never resend registration') from exc
    if failure: raise PreparationConflict('Public facts unavailable; negative history persisted; no success')
    return 'UPDATED'


def collect_preparation_gate(api, issue, policy):
    """Every Gate evaluation recomputes current phase evidence, never cached PASS."""
    if 'preparation_contract' not in policy: return None
    if type(policy['preparation_contract']) is not int or policy['preparation_contract'] != 2:
        raise PreparationConflict('Unsupported required preparation reader version')
    comment, record, prior = select_preparation(api.pages(f'/issues/{issue}/comments'), issue, policy)
    state = state_for_request(record, prior)
    facts = current_preparation_facts(api, record['input'], record, state)
    updated = preparation.resume(state, facts, (record['owner_facts'] or {}).get('observed_at') or comment['updated_at'])
    return {'contract': 2, 'input_digest': updated['input_digest'], 'pr': updated['input']['pr'],
            'head_sha': updated['input']['head_sha'], 'phase': updated['input']['phase'],
            'status': updated['status'], 'missing': updated['phase_evidence']['missing'],
            'next_owner': updated['next_owner'], 'next_action': updated['next_action'],
            'i01_live': updated['phase_evidence']['i01_live']}
