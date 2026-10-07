"""Public GitHub preparation transport. Writes are called ONLY by trusted main.

Separate owner input and writer snapshot markers; no Gate state mutation.
Comment PATCH lacks CAS: serialize in existing workflow, double-read before and
verify after write. Ambiguous writes raise and are never automatically retried.
"""
from __future__ import annotations
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
    fields = {'schema_version', 'repository', 'issue', 'purpose', 'owner', 'input_version',
              'input_digest', 'start_main_sha', 'observed_at', 'review', 'publication'}
    if not isinstance(record, dict) or set(record) != fields:
        raise PreparationConflict('Owner observation schema invalid')
    if (record['schema_version'] != 1 or record['repository'] != value['repository']
            or record['issue'] != value['issue'] or record['purpose'] != value['purpose']
            or record['owner'] != value['owner'] or record['input_version'] != value['input_version']
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
        if (review['id'] != value['work_automation_id'] or type(review['enabled']) is not bool
                or type(review['event_verified']) is not bool
                or not isinstance(review['target_event'], str) or not review['target_event']
                or not isinstance(review['actual_event'], str) or not review['actual_event']):
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
    if type(config.get('schema_version')) is not int or config.get('schema_version') != 1 or config.get('repository') != REPOSITORY:
        raise PreparationConflict('Main policy schema/repository invalid')
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
    # No dispatch state is transformed into preparation or Gate PASS.
    return facts


def authenticated_request(comment, issue, policy):
    body = comment.get('body', '')
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
        block(body[start:end], preparation.SNAPSHOT_START, preparation.SNAPSHOT_END)
        return body[:start] + content + body[end:]
    if preparation.SNAPSHOT_START in body:
        block(body, preparation.SNAPSHOT_START, preparation.SNAPSHOT_END)
        start = body.index(preparation.SNAPSHOT_START)
        end = body.index(preparation.SNAPSHOT_END) + len(preparation.SNAPSHOT_END)
        return body[:start] + content + body[end:]
    return body + '\n\n' + content


def reconcile_preparation(api, issue, policy, now):
    if type(issue) is not int or issue <= 0: raise PreparationConflict('Formal Issue ID unavailable')
    comments = api.pages(f'/issues/{issue}/comments')
    candidates = [c for c in comments if preparation.REQUEST_START in c.get('body', '')]
    if not candidates: return 'NO_RECORD'
    if len(candidates) != 1: raise PreparationConflict('Multiple preparation records; do not create another')
    comment = candidates[0]
    record = authenticated_request(comment, issue, policy)
    prior = snapshot(comment['body'])
    value = record['input']
    if prior:
        if prior['comment_id'] != comment['id']: raise PreparationConflict('Snapshot comment identity mismatch')
        state = preparation.rebase(prior['state'], value)
        if record['input_history'] != state['input_history']:
            raise PreparationConflict('Owner input transition history differs from saved history')
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
    first = read_facts(api, value)
    if record['owner_facts'] is not None:
        first.update(review={**copy.deepcopy(record['owner_facts']['review']),
                             'owner_observed_at': record['owner_facts']['observed_at']},
                     publication={**copy.deepcopy(record['owner_facts']['publication']),
                                  'owner_observed_at': record['owner_facts']['observed_at']})
    first['operations'] = reconcile_operations(api, issue, policy, state, first)
    second = read_facts(api, value)
    if record['owner_facts'] is not None:
        second.update(review={**copy.deepcopy(record['owner_facts']['review']),
                              'owner_observed_at': record['owner_facts']['observed_at']},
                      publication={**copy.deepcopy(record['owner_facts']['publication']),
                                   'owner_observed_at': record['owner_facts']['observed_at']})
    second['operations'] = reconcile_operations(api, issue, policy, state, second)
    latest = api.get(f'/issues/comments/{comment["id"]}')
    if first != second or latest != comment:
        raise PreparationConflict('Concurrent preparation edit/fact change; no write')
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
    body = replace_snapshot(comment['body'], content)
    if len(body.encode()) > 60000: raise PreparationConflict('Preparation comment exceeds bound')
    # There is no resend loop: transport errors may have committed remotely.
    try:
        written = api.request(api.root + f'/issues/comments/{comment["id"]}', 'PATCH', {'body': body})
        checked = api.get(f'/issues/comments/{comment["id"]}')
        after = read_facts(api, value)
        if record['owner_facts'] is not None:
            after.update(review={**copy.deepcopy(record['owner_facts']['review']),
                                 'owner_observed_at': record['owner_facts']['observed_at']},
                         publication={**copy.deepcopy(record['owner_facts']['publication']),
                                      'owner_observed_at': record['owner_facts']['observed_at']})
        after['operations'] = reconcile_operations(api, issue, policy, updated, after)
    except Exception as exc:
        raise PreparationWriteUnknown('Preparation write outcome unknown; inspect same comment before retry') from exc
    if written.get('id') != comment['id'] or checked.get('body') != body or after != second:
        raise PreparationWriteUnknown('Post-write conflict; stored snapshot is not certified; fresh read required')
    return 'UPDATED'
