#!/usr/bin/env python3
"""Issue102-only authenticated inbox and trusted-main manager.

GitHub account identity is the trust root, not a service Work run or local
secret possession. Only the serialized main workflow may call process_inbox.
Permanent refs and append-only bot journals must not be deleted or edited.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import urllib.error

try:
    from tools import startup_preparation as p, work_owner_resume as w, work_resume_claim as c
    from tools.automation_dashboard import BOT, REPOSITORY, author_matches, envelope, WorkRecordError
    from tools.update_automation_dashboard import GitHub
except ModuleNotFoundError:
    import startup_preparation as p
    import work_owner_resume as w
    import work_resume_claim as c
    from automation_dashboard import BOT, REPOSITORY, author_matches, envelope, WorkRecordError
    from update_automation_dashboard import GitHub

REQUEST = 'langbench-i01-request:v1'
JOURNAL = 'langbench-i01-journal:v1'
AMENDMENT = 'langbench-i01-amendment:v1'
SNAPSHOT = '<!-- langbench-i01-managed-snapshot:v1 -->'
REVIEW = 'langbench-manual-work-review:v1'
SCOPE = (102, 'work-owner-resume-i01-repair')


def encoded(marker, value):
    return '<!-- ' + marker + '\n' + p.canonical(value) + '\n-->'


def validate_extensions(issue, policy):
    if (issue, policy.get('purpose')) != SCOPE or policy.get('resume_protocol') != 2:
        raise ValueError('Management/manual review extensions are Issue102-only')
    manager = policy.get('i01_manager')
    if manager is not None:
        p.evidence_contract().fields(manager, {'schema_version','pr','base_comment_id','base_record_digest','authorization_ref'}, 'manager policy')
        if (type(manager['schema_version']) is not int or manager['schema_version'] != 1
                or manager['pr'] != 103 or type(manager['pr']) is not int
                or type(manager['base_comment_id']) is not int or manager['base_comment_id'] <= 0
                or not isinstance(manager['base_record_digest'], str) or not re.fullmatch('[a-f0-9]{64}', manager['base_record_digest'])
                or not isinstance(manager['authorization_ref'], str) or not manager['authorization_ref'].startswith('https://github.com/'+REPOSITORY+'/issues/102#issuecomment-')):
            raise ValueError('Invalid bounded manager policy')
    review = policy.get('manual_review')
    if review is not None:
        p.evidence_contract().fields(review, {'schema_version','pr','actor','delegation_ref','author'}, 'manual review policy')
        if (type(review['schema_version']) is not int or review['schema_version'] != 1
                or type(review['pr']) is not int or review['pr'] != 103 or review['author'] != policy['work_author']
                or review['actor'] != '/root/pr103_independent_review'
                or review['delegation_ref'] != 'https://github.com/'+REPOSITORY+'/pull/103#pullrequestreview-5475171001'):
            raise ValueError('Invalid explicit independent handoff policy')


def manual_review_records(reviews, issue, pr, policy):
    """Authenticate actual review transport before accepting inert payload.

    Shared GitHub account ownership cannot prove which Work authored a record;
    explicit human delegation and the independent author's own publication are
    operational assumptions. A COMMENT review remains a COMMENT review.
    """
    validate_extensions(issue, policy)
    expected = policy['manual_review']
    if pr != expected['pr']: return []
    accepted = []
    for review in reviews:
        if not author_matches(review.get('user'), expected['author']): continue
        body = review.get('body', '')
        value = envelope(body, REVIEW)
        if value is None:
            if isinstance(body,str) and body.lstrip().startswith('<!-- langbench-manual-work-review:'):
                raise WorkRecordError('Malformed manual independent review')
            continue
        fields = {'schema_version','kind','repository','issue','pr','head_sha','actor','delegation_ref',
                  'verdict','blockers','active_blocker','follow_up','follow_up_recorded','conditions'}
        if (set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
                or value['kind'] != 'manual_work_review' or value['repository'] != REPOSITORY
                or type(value['issue']) is not int or value['issue'] != issue
                or type(value['pr']) is not int or value['pr'] != pr
                or value['actor'] != expected['actor'] or value['delegation_ref'] != expected['delegation_ref']
                or not p.sha(value['head_sha']) or value['head_sha'] != review.get('commit_id')
                or type(review.get('id')) is not int or review['id'] <= 0
                or review.get('state') not in {'COMMENTED','APPROVED','CHANGES_REQUESTED'}):
            raise WorkRecordError('Manual review scope/actor/full HEAD/transport mismatch')
        try:
            p.timestamp(review.get('submitted_at'))
            from tools.automation_dashboard import validate_work_payload
        except ModuleNotFoundError:
            from automation_dashboard import validate_work_payload
        validate_work_payload(value)
        if review['state'] == 'CHANGES_REQUESTED' and value['verdict'] == 'PASS':
            raise WorkRecordError('Changes requested cannot publish PASS')
        value = copy.deepcopy(value)
        value['review_provenance'] = dict(route='manual_handoff',review_id=review['id'],actor=expected['actor'],
            delegation_ref=expected['delegation_ref'],github_review_state=review['state'],service_run_verified=False)
        accepted.append(((review['submitted_at'],review['id']),value))
    return accepted


def trusted_comment(comment, issue, author):
    if (not isinstance(comment,dict) or type(comment.get('id')) is not int or comment['id'] <= 0
            or comment.get('issue_url') != f'https://api.github.com/repos/{REPOSITORY}/issues/{issue}'
            or not author_matches(comment.get('user'),author) or not isinstance(comment.get('body'),str)):
        raise ValueError('Untrusted management comment transport')
    p.timestamp(comment.get('created_at'));p.timestamp(comment.get('updated_at'))
    if comment['created_at'] != comment['updated_at']:
        raise ValueError('Management records are immutable; edited record stopped')


def inbox(comments, issue, policy):
    validate_extensions(issue,policy)
    if 'i01_manager' not in policy: raise ValueError('Manager not enabled')
    requests = {}
    for comment in comments:
        body=comment.get('body','')
        if not isinstance(body,str):raise ValueError('Comment body unavailable')
        if not body.lstrip().startswith('<!-- langbench-i01-request:'):continue
        trusted_comment(comment,issue,policy['owner'])
        request=envelope(body,REQUEST)
        fields={'schema_version','kind','repository','issue','purpose','request_id','action',
                'expected_input_version','expected_input_digest','handoff','record'}
        if (not isinstance(request,dict) or set(request)!=fields
                or type(request['schema_version']) is not int or request['schema_version']!=1
                or request['kind']!='i01_management_request' or request['repository']!=REPOSITORY
                or type(request['issue']) is not int or request['issue']!=issue or request['purpose']!=policy['purpose']
                or request['action'] not in {'reserve','update'}
                or type(request['expected_input_version']) is not int or request['expected_input_version']<=0
                or not isinstance(request['expected_input_digest'],str) or not re.fullmatch('[a-f0-9]{64}',request['expected_input_digest'])
                or not isinstance(request['request_id'],str) or not re.fullmatch('[a-f0-9]{64}',request['request_id'])):
            raise ValueError('Malformed bounded manager request')
        if request['action']=='reserve':
            if request['record'] is not None:raise ValueError('Reserve cannot edit preparation')
            value=bound_handoff(request,comment['id'])
            if value['pr']!=policy['i01_manager']['pr'] or any(value[k] is not None for k in ('claim','receipt','next_action','recheck')):
                raise ValueError('Reservation request cannot claim execution results')
        elif request['handoff'] is not None or not isinstance(request['record'],dict):
            raise ValueError('Update must supply only a preparation proposal')
        existing=requests.get(request['request_id'])
        if existing and existing[1]!=request:raise ValueError('Duplicate request ID with different payload')
        if not existing or comment['id']<existing[0]['id']:requests[request['request_id']]=(comment,request)
    return requests


def bound_handoff(request, comment_id):
    value=copy.deepcopy(request['handoff'])
    if not isinstance(value,dict):raise ValueError('Reservation handoff missing')
    identity=value.get('work',{}).get('identity',{})
    if identity.get('route')!='managed' or identity.get('authorization_comment_id') is not None:
        raise ValueError('Managed request must leave transport comment ID unclaimed')
    identity['authorization_comment_id']=comment_id
    return w.validate(value)


def authenticate_managed_handoff(value, comments, policy):
    requests=inbox(comments,value['issue'],policy)
    ident=value['work']['identity']['authorization_comment_id']
    selected=[(comment,request) for comment,request in requests.values() if comment['id']==ident and request['action']=='reserve']
    if len(selected)!=1 or c.binding(bound_handoff(selected[0][1],ident))!=c.binding(value):
        raise ValueError('Managed handoff does not bind authenticated canonical reservation request')
    return selected[0][1]


def bot_records(comments, marker, issue):
    out=[]
    for comment in comments:
        body=comment.get('body','')
        if not isinstance(body,str):raise ValueError('Comment body unavailable')
        if not body.lstrip().startswith('<!-- '+marker.split(':')[0]+':'):continue
        trusted_comment(comment,issue,BOT)
        value=envelope(body,marker)
        if value is None:raise ValueError('Malformed manager-owned record')
        out.append((comment,value))
    return out


def record_digest(record):
    return p.digest(record)


def effective_preparation(comments, base, record, issue, policy):
    """One owner base + one nonbranching bot amendment chain, never two inputs."""
    from_module = _preparation()
    validate_extensions(issue,policy)
    config=policy['i01_manager']
    if base['id']!=config['base_comment_id'] or record_digest(record)!=config['base_record_digest']:
        raise ValueError('Pinned preparation base changed; human reconciliation required')
    requests=inbox(comments,issue,policy)
    amendments=bot_records(comments,AMENDMENT,issue)
    current=copy.deepcopy(record);remaining=list(amendments);seen=set()
    while remaining:
        matches=[item for item in remaining if item[1].get('previous_record_digest')==record_digest(current)]
        if len(matches)!=1:raise ValueError('Missing/branched amendment chain')
        item,value=matches[0];remaining.remove(matches[0])
        fields={'schema_version','kind','base_comment_id','previous_record_digest','request_id','request_digest','record'}
        if set(value)!=fields or type(value['schema_version']) is not int or value['schema_version']!=1 or value['kind']!='i01_preparation_amendment' or value['base_comment_id']!=base['id']:
            raise ValueError('Invalid amendment identity')
        selected=requests.get(value['request_id'])
        if (selected is None or selected[1]['action']!='update' or selected[1]['record']!=value['record']
                or p.digest(selected[1])!=value['request_digest'] or value['request_id'] in seen):
            raise ValueError('Amendment does not bind authenticated update request')
        validate_update(current,selected[1],issue,policy)
        current=from_module.validate_request_v2(copy.deepcopy(value['record']),issue,policy)
        seen.add(value['request_id'])
    snapshots=[x for x in comments if SNAPSHOT in x.get('body','')]
    if len(snapshots)>1:raise ValueError('Multiple managed snapshots')
    prior=from_module.snapshot(base['body'])
    if snapshots:
        saved=snapshots[0]
        if (not author_matches(saved.get('user'),BOT) or saved.get('issue_url')!=f'https://api.github.com/repos/{REPOSITORY}/issues/{issue}'
                or not saved['body'].startswith(SNAPSHOT+'\n') or type(saved.get('id')) is not int):
            raise ValueError('Untrusted managed snapshot')
        prior=from_module.snapshot(saved['body'])
        if prior is None and saved['body']!=SNAPSHOT+'\n' or prior is not None and prior['comment_id']!=saved['id']:raise ValueError('Managed snapshot identity missing')
    return base,current,prior


def _preparation():
    try:
        from tools import preparation_github
    except ModuleNotFoundError:
        import preparation_github
    return preparation_github


def validate_update(current, request, issue, policy):
    if (request['expected_input_version']!=current['input_version'] or request['expected_input_digest']!=current['input_digest']):
        raise ValueError('Stale input version/digest; no update')
    candidate=_preparation().validate_request_v2(copy.deepcopy(request['record']),issue,policy)
    old,new=current['input'],candidate['input']
    mutable={'input_version','phase','head_sha','registration_prompts'}
    if any(old[k]!=new[k] for k in old if k not in mutable) or new['input_version']!=old['input_version']+1:
        raise ValueError('Update changes immutable scope or skips input version')
    if candidate['input_history']!=current['input_history']+[old] or any(candidate[k]!=current[k] for k in ('operations','legacy_operations')):
        raise ValueError('Update removed immutable input/intent history')
    phases=['PRE_IMPLEMENTATION','PR_BOUND','PRE_MERGE','POST_MERGE','FINISHED']
    if phases.index(new['phase'])<phases.index(old['phase']):raise ValueError('Preparation phase cannot regress')
    owner=candidate['owner_facts']
    if (current['owner_facts'] or {}).get('execution') is not None and owner is not None and owner['execution'] is None:
        raise ValueError('Retained execution cannot be removed')
    if owner is None:raise ValueError('Update requires explicit owner observations')
    if owner['execution'] is not None:
        value=owner['execution']
        if value['work']['identity']['route']!='managed' or value['claim'] is None:
            raise ValueError('Execution update requires managed permanent reservation')
    return candidate


def publish(api, issue, marker, value):
    body=encoded(marker,value)
    _preparation().validate_comment_capacity(body)
    # One POST, never retry. Persisted duplicates/edited records fail closed.
    saved=api.request(api.root+f'/issues/{issue}/comments','POST',{'body':body})
    checked=api.get(f'/issues/comments/{saved["id"]}')
    trusted_comment(checked,issue,BOT)
    if checked['body']!=body:raise ValueError('Manager journal publication UNKNOWN')
    return checked


def journal_entries(comments, request, value):
    entries={}
    for _,entry in bot_records(comments,JOURNAL,value['issue']):
        fields={'schema_version','kind','request_id','request_digest','binding','stage','commit_sha'}
        if (set(entry)!=fields or type(entry['schema_version']) is not int or entry['schema_version']!=1
                or entry['kind']!='i01_send_journal' or entry['stage'] not in {'commit','ref','acquired'}
                or not isinstance(entry['request_id'],str) or not re.fullmatch('[a-f0-9]{64}',entry['request_id'])):
            raise ValueError('Invalid persistent send journal')
        if entry['request_id']!=request['request_id']:continue
        if entry['request_digest']!=p.digest(request) or entry['binding']!=c.binding(value) or entry['stage'] in entries:
            raise ValueError('Journal duplicate/binding conflict')
        if (entry['stage']=='commit' and entry['commit_sha'] is not None or entry['stage']!='commit' and not p.sha(entry['commit_sha'])):
            raise ValueError('Journal phase/commit mismatch')
        entries[entry['stage']]=entry
    if ('ref' in entries and 'commit' not in entries or 'acquired' in entries and 'ref' not in entries
            or 'acquired' in entries and entries['acquired']['commit_sha']!=entries['ref']['commit_sha']):
        raise ValueError('Incomplete journal prefix; never reset')
    return entries


def attempt_reservation(api, request, value, comments):
    entries=journal_entries(comments,request,value)
    if entries:
        # A previous commit POST may have been sent. Unknown commit cannot be recreated.
        if 'ref' not in entries:raise ValueError('Commit result UNKNOWN; retained journal; GET only')
        saved=c.read_reservation(api,value)
        if saved['record']!=c.binding(value) or saved['commit_sha']!=entries['ref']['commit_sha']:
            raise ValueError('Permanent reservation differs; no takeover')
        return saved
    api.check_write_ready()
    # A different durable request for the same slot may have sent a commit before
    # ref creation. It fences the operation even if its ref is still absent.
    for _,other in bot_records(comments,JOURNAL,value['issue']):
        if other.get('binding',{}).get('dedup_key')==w.key(value) and other.get('request_id')!=request['request_id']:
            raise ValueError('Operation has another retained send journal; no fresh attempt')
    matches=api.get('/git/matching-refs/'+c.reservation_ref(value).removeprefix('refs/'))
    if not isinstance(matches,list) or matches:
        raise ValueError('Permanent operation slot already exists/unavailable; no send')
    base=api.get('/git/commits/'+value['merge_sha'])
    if base.get('sha')!=value['merge_sha'] or not p.sha(base.get('tree',{}).get('sha')):raise ValueError('Merge tree unavailable')
    def persist(stage,sha):
        entry=dict(schema_version=1,kind='i01_send_journal',request_id=request['request_id'],request_digest=p.digest(request),binding=c.binding(value),stage=stage,commit_sha=sha)
        publish(api,value['issue'],JOURNAL,entry)
    persist('commit',None)
    commit=api.request(api.root+'/git/commits','POST',dict(message=p.canonical(c.binding(value)),tree=base['tree']['sha'],parents=[value['merge_sha']]))
    if not p.sha(commit.get('sha')):raise ValueError('Commit result UNKNOWN; no ref send')
    persist('ref',commit['sha'])
    try:
        api.request(api.root+'/git/refs','POST',dict(ref=c.reservation_ref(value),sha=commit['sha']))
    except (OSError,ValueError):pass
    saved=c.read_reservation(api,value)
    if saved['record']!=c.binding(value) or saved['commit_sha']!=commit['sha']:raise ValueError('Reservation collision/UNKNOWN')
    persist('acquired',commit['sha'])
    return saved


def process_inbox(api, issue, policy):
    """Scan durable inbox each wake; no FIFO or event delivery assumption."""
    if not policy.get('i01_manager'):return 'NOT_ENABLED'
    comments=api.pages(f'/issues/{issue}/comments');requests=inbox(comments,issue,policy)
    completed=0
    # Canonical IDs, not delivery order. Same-version branches stop before writes.
    pending_updates=[r for _,r in requests.values() if r['action']=='update']
    expected={}
    for r in pending_updates:
        pair=(r['expected_input_version'],r['expected_input_digest'])
        if pair in expected and expected[pair]!=r['request_id']:raise ValueError('Competing updates for the same input version')
        expected[pair]=r['request_id']
    for source,request in sorted(requests.values(),key=lambda item:item[0]['id']):
        comments=api.pages(f'/issues/{issue}/comments')
        base,record,_=_preparation().select_preparation(comments,issue,policy)
        if request['action']=='reserve':
            value=bound_handoff(request,source['id'])
            api.bind(value)
            entries=journal_entries(comments,request,value)
            # Fresh observations always precede writes/recovery. Request remains
            # valid across later managed versions if it is in immutable history.
            versions=record['input_history']+[record['input']]
            if not any(v['input_version']==request['expected_input_version'] and p.digest(v)==request['expected_input_digest'] for v in versions):
                raise ValueError('Reservation input version/digest unavailable')
            if not entries and (request['expected_input_version']!=record['input_version'] or request['expected_input_digest']!=record['input_digest']):
                raise ValueError('New reservation uses stale input')
            reader=w.ObservationGitHub(api.token)
            first=w.read_facts(reader,value,include_reservation=False)
            second=w.read_facts(reader,value,include_reservation=False)
            if first!=second:raise ValueError('Reservation public facts changed')
            if w.observe(value,first)['reason']!='Single-owner claim missing; no next operation':
                raise ValueError('Reservation preflight blocked')
            attempt_reservation(api,request,value,comments)
        else:
            done=[v for _,v in bot_records(comments,AMENDMENT,issue) if v.get('request_id')==request['request_id']]
            if done:continue
            candidate=validate_update(record,request,issue,policy)
            pull=api.get(f'/pulls/{policy["i01_manager"]["pr"]}')
            if (pull.get('head',{}).get('sha')!=candidate['input']['head_sha'] or pull.get('base',{}).get('ref')!='main'
                    or pull.get('base',{}).get('repo',{}).get('full_name')!=REPOSITORY):raise ValueError('Proposed input HEAD differs from actual PR')
            execution=candidate['owner_facts']['execution']
            if execution is not None:
                authenticate_managed_handoff(execution,comments,policy)
                saved=c.read_reservation(api,execution)
                if c.check_reservation(execution,saved):raise ValueError('Update reservation changed/missing')
                prior_execution=(record['owner_facts'] or {}).get('execution')
                if prior_execution is not None and c.binding(prior_execution)!=c.binding(execution):raise ValueError('Cannot switch reserved execution')
            # Re-read complete transport and current API target immediately before
            # immutable publication. External administrative races remain detectable.
            if comments!=api.pages(f'/issues/{issue}/comments') or pull!=api.get(f'/pulls/{pull["number"]}'):
                raise ValueError('Input/PR changed before amendment publication')
            publish(api,issue,AMENDMENT,dict(schema_version=1,kind='i01_preparation_amendment',base_comment_id=base['id'],previous_record_digest=record_digest(record),request_id=request['request_id'],request_digest=p.digest(request),record=candidate))
            _preparation().select_preparation(api.pages(f'/issues/{issue}/comments'),issue,policy)
        completed+=1
    return f'RECONCILED {completed}'


class ManagerGitHub(c.ReservationGitHub):
    def __init__(self,token):
        GitHub.__init__(self,token);self.value=None;self.created_commit=None
    def bind(self,value):
        if value['work']['identity']['route']!='managed':raise ValueError('Only managed reservation accepted')
        self.value=copy.deepcopy(value);self.created_commit=None
    def request(self,path,method='GET',data=None,raw=False):
        if method=='GET':return GitHub.request(self,path,method,data,raw)
        self.check_write_ready()
        if method=='POST' and path==self.root+'/issues/102/comments' and not raw:
            body=(data or {}).get('body')
            if set(data or {})!={'body'} or not any(envelope(body,marker) is not None for marker in (JOURNAL,AMENDMENT)):
                raise ValueError('Manager can only append bounded journal/amendment records')
            return self._send_request(path,method,data)
        if self.value is None:raise ValueError('No authenticated reservation bound')
        return super().request(path,method,data,raw)


def reconcile_managed_preparation(api,issue,policy,now):
    """Keep original owner comment intact. Only bot-owned snapshot is mutable."""
    pg=_preparation();comments=api.pages(f'/issues/{issue}/comments')
    base,record,prior=pg.select_preparation(comments,issue,policy)
    state=pg.state_for_request(record,prior)
    failure=False
    try:
        first=pg.current_preparation_facts(api,record['input'],record,state)
        second=pg.current_preparation_facts(api,record['input'],record,state)
        if first!=second:raise ValueError('Managed preparation public facts changed')
        updated=p.resume(state,second,now)
    except (OSError,KeyError,TypeError,ValueError):
        updated=pg.preserve_negative_failure(state,record,now)
        failure=True
        second=None
    snapshots=[x for x in comments if SNAPSHOT in x.get('body','')]
    target=snapshots[0] if snapshots else None
    before=api.pages(f'/issues/{issue}/comments')
    if before!=comments:raise ValueError('Managed preparation inbox changed')
    if target is None:
        # Snapshot creation has no ref/operation side effects. Lost POST result is
        # discovered by unique marker on next GET; no speculative same-run retry.
        saved=api.request(api.root+f'/issues/{issue}/comments','POST',{'body':SNAPSHOT+'\n'})
        target=api.get(f'/issues/comments/{saved["id"]}')
        if target.get('body')!=SNAPSHOT+'\n' or not author_matches(target.get('user'),BOT):raise ValueError('Snapshot create UNKNOWN')
    body=pg.preparation_body_v2(target,updated,record)
    if target['body']==body:
        if failure:raise ValueError('Public facts unavailable; retained negative history')
        return 'NO_OP'
    written=api.request(api.root+f'/issues/comments/{target["id"]}','PATCH',{'body':body})
    checked=api.get(f'/issues/comments/{target["id"]}')
    if checked.get('body')!=body or written.get('body')!=body or not author_matches(checked.get('user'),BOT):raise ValueError('Managed snapshot write UNKNOWN')
    _,after,_=pg.select_preparation(api.pages(f'/issues/{issue}/comments'),issue,policy)
    if after!=record or not failure and pg.current_preparation_facts(api,record['input'],record,state)!=second:raise ValueError('Managed snapshot facts changed after write')
    if failure:raise ValueError('Public facts unavailable; negative history persisted')
    return 'UPDATED'


def read_response(api, request_comment_id, policy):
    """Public GET-only receipt; missing/unknown is pending, never a resend permit."""
    if type(request_comment_id) is not int or request_comment_id<=0:raise ValueError('Invalid request comment ID')
    comments=api.pages('/issues/102/comments')
    requests=inbox(comments,102,policy)
    matching=[x for x in requests.values() if x[0]['id']==request_comment_id]
    if len(matching)!=1:raise ValueError('Canonical authenticated request is missing')
    source,request=matching[0]
    if request['action']=='update':
        _,record,_=_preparation().select_preparation(comments,102,policy)
        amendments=[v for _,v in bot_records(comments,AMENDMENT,102) if v['request_id']==request['request_id']]
        return dict(status='APPLIED' if amendments else 'PENDING',request_id=request['request_id'],current_record=record)
    value=bound_handoff(request,source['id'])
    entries=journal_entries(comments,request,value)
    if not entries:return dict(status='PENDING',request_id=request['request_id'],handoff=None)
    if 'ref' not in entries:return dict(status='UNKNOWN',request_id=request['request_id'],handoff=None)
    try:
        saved=c.read_reservation(api,value)
    except urllib.error.HTTPError as error:
        if error.code==404:return dict(status='UNKNOWN',request_id=request['request_id'],handoff=None)
        raise
    if saved['record']!=c.binding(value) or saved['commit_sha']!=entries['ref']['commit_sha']:raise ValueError('Reservation receipt binding changed')
    value['claim']=dict(dedup_key=w.key(value),execution_id=w.execution_id(value),owner='Work(root)',status='RUNNING',
        ref=saved['ref'],commit_sha=saved['commit_sha'],evidence_url='https://github.com/'+REPOSITORY+'/commit/'+saved['commit_sha'],
        observed_at=datetime.now(timezone.utc).isoformat())
    return dict(status='ACQUIRED',request_id=request['request_id'],handoff=w.validate(value))


def build_request(record, *, handoff=None, update=None, request_id=None):
    """Local inert request builder. Public nonce is not a possession credential."""
    if (handoff is None) == (update is None):raise ValueError('Choose reservation or update')
    ident=request_id or hashlib.sha256(os.urandom(32)).hexdigest()
    value=None
    if handoff is not None:
        value=copy.deepcopy(handoff)
        if value.get('schema_version')!=2 or any(value.get(k) is not None for k in ('claim','receipt','next_action','recheck')):
            raise ValueError('Managed reservation needs unclaimed v2 handoff')
        value['work']['identity']=dict(scheme='github_actor_v1',source='github_issue_comment',assurance='github_actor_not_service_run',route='managed',
            public_id=hashlib.sha256(os.urandom(32)).hexdigest(),conversation_id=value['work'].get('identity',{}).get('conversation_id'),
            cloud_task_id=value['work'].get('identity',{}).get('cloud_task_id'),authorization_comment_id=None)
    return dict(schema_version=1,kind='i01_management_request',repository=REPOSITORY,issue=102,purpose=SCOPE[1],request_id=ident,
        action='reserve' if handoff is not None else 'update',expected_input_version=record['input_version'],expected_input_digest=record['input_digest'],handoff=value,record=copy.deepcopy(update))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--process-inbox',action='store_true')
    parser.add_argument('--read-response',type=int,metavar='REQUEST_COMMENT_ID')
    parser.add_argument('--request',type=Path,help='Validate/encode an inert request; no network mutation')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--preparation-record',type=Path)
    parser.add_argument('--reserve-handoff',type=Path)
    parser.add_argument('--update-record',type=Path)
    parser.add_argument('--request-id',help='Reuse the same saved request; never regenerate after an ambiguous submission')
    parser.add_argument('--config',type=Path,default=Path('.github/automation-dashboard.json'))
    args=parser.parse_args()
    if args.process_inbox and any((args.read_response,args.request,args.preparation_record,args.reserve_handoff,args.update_record)):parser.error('Choose inbox or local request generation')
    config=p.loads(args.config.read_text(encoding='utf-8'))
    try:
        from tools.automation_dashboard import validate_policy_config
    except ModuleNotFoundError:
        from automation_dashboard import validate_policy_config
    validate_policy_config(config);policy=config['issues']['102']
    if args.read_response is not None:
        if any((args.request,args.preparation_record,args.reserve_handoff,args.update_record)):parser.error('Choose response read or request generation')
        result=read_response(w.ObservationGitHub(os.environ.get('GH_TOKEN')),args.read_response,policy)
        if args.output is not None:w.save_observation(args.output,result)
        else:print(p.canonical(result))
        return 0 if result['status'] in {'ACQUIRED','APPLIED'} else 1
    if args.request is not None or args.preparation_record is not None:
        if args.request is not None:
            if any((args.reserve_handoff,args.update_record,args.preparation_record)):parser.error('Choose saved request or generator')
            request=p.loads(args.request.read_text(encoding='utf-8'))
        else:
            request=build_request(p.loads(args.preparation_record.read_text(encoding='utf-8')),
                handoff=p.loads(args.reserve_handoff.read_text(encoding='utf-8')) if args.reserve_handoff else None,
                update=p.loads(args.update_record.read_text(encoding='utf-8')) if args.update_record else None,request_id=args.request_id)
        body=encoded(REQUEST,request)
        now=datetime.now(timezone.utc).isoformat()
        inbox([dict(id=1,issue_url=f'https://api.github.com/repos/{REPOSITORY}/issues/102',user=policy['owner'],body=body,created_at=now,updated_at=now)],102,policy)
        if args.output is not None:
            # O_EXCL preserves the request nonce/binding across an ambiguous send.
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(body+'\n');stream.flush();os.fsync(stream.fileno())
        else:print(body)
        return 0
    if not args.process_inbox:parser.error('Choose --request or --process-inbox')
    if os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY or not os.environ.get('GITHUB_ACTIONS')=='true':raise ValueError('Trusted workflow context required')
    api=ManagerGitHub(os.environ.get('GH_TOKEN'))
    try:
        print(process_inbox(api,102,policy));return 0
    except (OSError,ValueError,KeyError,TypeError):
        print('::error::Issue102 manager STOPPED; retain inbox/journal/ref; no retry or success certification');return 1


if __name__=='__main__':raise SystemExit(main())
