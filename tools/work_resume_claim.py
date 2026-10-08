"""I-01 one-shot ownership reservation, not a Work run ID or renewable lease.

GitHub create-ref is the only atomic exclusion primitive used. References must
never be updated/deleted by participants. Repository administrators remain the
trust root; ref integrity and account authorization are operational assumptions.
Only repeatable read-only smoke/safe-stop observations are authorized here.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sys

try:
    from tools import startup_preparation as p, work_owner_resume as w
    from tools.update_automation_dashboard import GitHub
    from tools.automation_dashboard import author_matches, envelope
except ModuleNotFoundError:
    import startup_preparation as p
    import work_owner_resume as w
    from update_automation_dashboard import GitHub
    from automation_dashboard import author_matches, envelope

PREFIX = 'refs/tags/langbench-i01-resume-'
ASSURANCE = 'bearer_possession_not_service_run'


def reservation_ref(value):
    # Delivery is intentionally excluded: redelivery/new delivery for the same
    # operation competes for the SAME permanent slot.
    return PREFIX + hashlib.sha256(w.key(value).encode()).hexdigest()


def validate_identity(value):
    work = value['work']
    if not isinstance(work, dict) or set(work) != {'run_id', 'automation_id', 'started_at', 'evidence_url', 'observed_at', 'identity'}:
        raise ValueError('Missing explicit capability identity')
    if work['run_id'] is not None:
        raise ValueError('Capability route must report unavailable Work run_id as null')
    if not isinstance(work['automation_id'], str) or not p.re.fullmatch('[a-f0-9]{32}', work['automation_id']):
        raise ValueError('Invalid automation registration identity')
    identity = work['identity']
    if not isinstance(identity, dict) or set(identity) != {'scheme', 'public_id', 'source', 'assurance', 'route', 'conversation_id', 'cloud_task_id', 'authorization_comment_id'}:
        raise ValueError('Invalid execution capability fields')
    if (identity['scheme'] != 'capability_v1' or identity['source'] != 'local_csprng'
            or identity['assurance'] != ASSURANCE or identity['route'] not in {'automatic', 'manual'}
            or not isinstance(identity['public_id'], str) or not p.re.fullmatch('[a-f0-9]{64}', identity['public_id'])):
        raise ValueError('Capability identity scheme/source/assurance invalid')
    # Context IDs are diagnostics supplied by owner, not credential assertions.
    for name in ('conversation_id', 'cloud_task_id'):
        if identity[name] is not None and (not isinstance(identity[name], str) or not identity[name].strip()):
            raise ValueError('Context identity is invalid')
    if identity['public_id'] in {work['automation_id'], value['event']['delivery_id'], identity['conversation_id'], identity['cloud_task_id']}:
        raise ValueError('Different identity kind reused as execution capability')
    comment = identity['authorization_comment_id']
    if identity['route'] == 'manual':
        if type(comment) is not int or comment <= 0: raise ValueError('Manual route needs human authorization comment')
    elif comment is not None: raise ValueError('Automatic route cannot claim manual authorization')
    w.evidence(work)
    if w.instant(work['observed_at']) < w.instant(work['started_at']): raise ValueError('Work observation predates start')


def validate_records(value):
    authorization=value['authorization']
    if not isinstance(authorization,dict) or set(authorization)!={'kind','authorization_ref','effect'} or authorization['kind'] not in {'live_smoke','safe_stop'} or authorization['effect']!='read_only' or not isinstance(authorization['authorization_ref'],str) or not authorization['authorization_ref']:
        raise ValueError('Explicit read-only authorization binding required')
    public_id = value['work']['identity']['public_id']
    for name in ('claim', 'receipt', 'next_action'):
        item = value[name]
        if item is None: continue
        expected = {
            'claim': {'dedup_key','execution_id','owner','status','evidence_url','observed_at','ref','commit_sha'},
            'receipt': {'execution_id','waiting_comment_id','waiting_body_sha256','evidence_url','observed_at'},
            'next_action': {'execution_id','dedup_key','kind','status','authorization_ref','evidence_url','observed_at','effect'},
        }[name]
        if not isinstance(item,dict) or set(item) != expected or item['execution_id'] != public_id:
            raise ValueError('Capability record binding differs')
        w.evidence(item)
        if name in {'claim','next_action'} and item['dedup_key'] != w.key(value): raise ValueError('Operation scope differs')
        if name == 'claim' and (item['owner'] != 'Work(root)' or item['ref'] != reservation_ref(value)
                or not p.sha(item['commit_sha']) or item['status'] not in {'RUNNING','UNKNOWN','FAILED','CANCELLED'}):
            raise ValueError('Invalid atomic reservation claim')
        if name == 'receipt' and (item['waiting_comment_id'] != value['waiting_record']['comment_id']
                or item['waiting_body_sha256'] != value['waiting_record']['body_sha256']):
            raise ValueError('Receipt/waiting binding differs')
        if name == 'next_action' and (item['kind'] not in {'live_smoke','safe_stop'}
                or item['effect'] not in {'read_only','external_write'}
                or item['status'] not in {'EXECUTED','UNKNOWN','FAILED','CANCELLED','NO_OP'}
                or not isinstance(item['authorization_ref'],str) or not item['authorization_ref']):
            raise ValueError('Invalid operation observation')
    if value['next_action'] is not None and any(value['next_action'][k]!=authorization[k] for k in ('kind','authorization_ref')):
        raise ValueError('Next operation differs from reserved authorization')
    # A second registration is an external side effect, not an implicit retry.
    if value['work']['identity']['route']=='manual' and value['claim'] is not None:
        raise ValueError('Manual read-only authorization is not automatic claim takeover')
    if value['recheck'] is not None: raise ValueError('Capability route does not authorize recheck registration')


def binding(value):
    return dict(schema_version=1, kind='i01_owner_reservation', repository=value['repository'],
                issue=value['issue'], purpose=value['purpose'], dedup_key=w.key(value),
                pr=value['pr'], reviewed_head_sha=value['reviewed_head_sha'], merge_sha=value['merge_sha'],
                owner=copy.deepcopy(value['owner']), waiting_record=copy.deepcopy(value['waiting_record']),
                event=copy.deepcopy(value['event']), work=copy.deepcopy(value['work']),
                allowed_effect='read_only', authorization=copy.deepcopy(value['authorization']))


def read_reservation(api, value):
    ref = api.get('/git/ref/' + reservation_ref(value).removeprefix('refs/'))
    obj = ref['object']
    if ref.get('ref') != reservation_ref(value) or obj.get('type') != 'commit' or not p.sha(obj.get('sha')):
        raise ValueError('Reservation ref identity changed')
    commit = api.get('/git/commits/' + obj['sha'])
    if commit.get('sha') != obj['sha'] or [x.get('sha') for x in commit.get('parents',[])] != [value['merge_sha']]:
        raise ValueError('Reservation commit target differs')
    record = p.loads(commit['message'])
    return {'ref':ref['ref'], 'commit_sha':obj['sha'], 'record':record}


def check_reservation(value, saved):
    if not isinstance(saved,dict) or set(saved) != {'ref','commit_sha','record'}:
        return 'Atomic GitHub ref reservation unavailable; comments/local locks are not exclusion'
    claim = value['claim']
    if saved['record'] != binding(value): return 'Different capability/event/target reserved; do not take over or resend'
    if not claim or saved['ref'] != claim['ref'] or saved['commit_sha'] != claim['commit_sha']:
        return 'Reservation receipt changed or missing'
    action = value['next_action']
    if action and action['effect'] != 'read_only':
        return 'External write is not authorized by this read-only reservation; no cross-service atomicity'
    return None


def check_manual(value, comments):
    identity=value['work']['identity']
    matches=[c for c in comments if c.get('id')==identity['authorization_comment_id']]
    expected=dict(schema_version=1,kind='i01_manual_read_only',binding=binding(value),
                  retained_automatic_status='UNVERIFIED',allowed_effect='read_only')
    if len(matches)!=1 or not author_matches(matches[0].get('user'),value['owner']):
        return 'Human manual authorization unavailable or untrusted'
    if envelope(matches[0].get('body'),'langbench-i01-manual:v1')!=expected:
        return 'Manual authorization must bind current owner/event/target/waiting/capability'
    action=value['next_action']
    if action and action['effect']!='read_only':return 'Manual read-only handling does not fence an existing execution; external write stopped'
    return None


def verify_possession(value, secret):
    if not isinstance(secret,str) or not p.re.fullmatch('[a-f0-9]{64}',secret) or not hmac.compare_digest(hashlib.sha256(bytes.fromhex(secret)).hexdigest(),value['work']['identity']['public_id']):
        raise ValueError('Execution capability possession mismatch')


def acquire(api, value, secret, journal, persist):
    """One create-ref attempt. Ambiguous results are GET-reconciled, never resent.

    The private secret authenticates local possession, not a service execution.
    It must be fsynced before calling this function; never publish it.
    """
    w.validate(value)
    if value['schema_version'] != 2 or value['work']['identity']['route'] != 'automatic':
        raise ValueError('Only explicit automatic capability reservations may be acquired')
    verify_possession(value,secret)
    refname = reservation_ref(value)
    if journal:
        # A durable ATTEMPTING/UNKNOWN/ACQUIRED journal is never a send permit.
        if journal.get('binding') != binding(value): raise ValueError('Saved attempt binding differs')
        saved=read_reservation(api,value)
        if saved['record'] != binding(value) or saved['commit_sha'] != journal.get('commit_sha'):
            raise ValueError('Uncertain reservation needs human reconciliation')
        return saved
    # List exact name via matching-refs: an empty complete response proves absence.
    matches = api.get('/git/matching-refs/' + refname.removeprefix('refs/'))
    if not isinstance(matches,list): raise ValueError('Reservation listing unavailable')
    if matches:
        saved = read_reservation(api,value)
        if saved['record'] != binding(value): raise ValueError('Another capability already owns this operation')
        journal.update(status='ACQUIRED',binding=binding(value),ref=refname,commit_sha=saved['commit_sha'])
        persist(journal)
        return saved # recovered uncertain create; no POST
    base = api.get('/git/commits/' + value['merge_sha'])
    if base.get('sha') != value['merge_sha'] or not p.sha(base.get('tree',{}).get('sha')):
        raise ValueError('Current merge commit unavailable')
    commit = api.request(api.root+'/git/commits','POST',dict(message=p.canonical(binding(value)),
                         tree=base['tree']['sha'],parents=[value['merge_sha']]))
    if not p.sha(commit.get('sha')): raise ValueError('Reservation commit result UNKNOWN; no ref send')
    journal.update(status='ATTEMPTING',binding=binding(value),ref=refname,commit_sha=commit['sha'])
    persist(journal) # Must complete before any create-ref attempt.
    try:
        api.request(api.root+'/git/refs','POST',dict(ref=refname,sha=commit['sha']))
    except (OSError,ValueError):
        # A collision, timeout, or ambiguous response requires the same real ref.
        # No retries, ref updates/deletes, expiration, or owner selection by time.
        pass
    saved = read_reservation(api,value)
    if saved['record'] != binding(value) or saved['commit_sha'] != commit['sha']:
        raise ValueError('Reservation lost/UNKNOWN; retain local capability and stop')
    return saved


class ReservationGitHub(GitHub):
    """Only two purpose-bound git-data POSTs; no comment/PATCH/ref update/delete."""
    def __init__(self, token, value):
        super().__init__(token)
        self.value=copy.deepcopy(value)
        self.created_commit=None

    def request(self, path, method='GET', data=None, raw=False):
        if method=='GET':return super().request(path,method,data,raw)
        if method!='POST' or raw or not self.token:
            raise ValueError('I-01 reservation requires configured contents-write token; no other mutation supported')
        if path==self.root+'/git/commits':
            base=self.get('/git/commits/'+self.value['merge_sha'])
            expected=dict(message=p.canonical(binding(self.value)),tree=base['tree']['sha'],parents=[self.value['merge_sha']])
            if data!=expected:raise ValueError('Reservation commit scope differs')
            result=self._send_request(path,method,data)
            self.created_commit=result.get('sha')
            return result
        if path==self.root+'/git/refs' and self.created_commit is not None:
            if data!=dict(ref=reservation_ref(self.value),sha=self.created_commit):
                raise ValueError('Reservation ref scope differs')
            return self._send_request(path,method,data)
        raise ValueError('Only bound I-01 commit/ref creation is permitted')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff',required=True,type=Path)
    parser.add_argument('--capability-file',required=True,type=Path)
    parser.add_argument('--state',required=True,type=Path)
    parser.add_argument('--sync-artifact-zip',type=Path)
    parser.add_argument('--initialize',action='store_true',help='Create private capability only; no network')
    args=parser.parse_args()
    if args.initialize:
        args.capability_file.parent.mkdir(parents=True,exist_ok=True)
        secret=secrets.token_hex(32)
        # O_EXCL prevents replacing a capability after crash or lost response.
        fd=os.open(args.capability_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(secret+'\n');stream.flush();os.fsync(stream.fileno())
        print(p.canonical({'scheme':'capability_v1','public_id':hashlib.sha256(bytes.fromhex(secret)).hexdigest(),
                           'source':'local_csprng','assurance':ASSURANCE}))
        return 0
    try:
        value=w.validate(p.loads(args.handoff.read_text(encoding='utf-8')))
        api=ReservationGitHub(os.environ.get('GH_TOKEN'),value)
        # Fresh bound Issue/PR/waiting/policy must precede a claim write.
        reader=w.ObservationGitHub(os.environ.get('GH_TOKEN'),args.sync_artifact_zip)
        # Reservation does not yet exist; collect ordinary scope without a ref.
        facts=w.read_facts(reader,value,include_reservation=False)
        if p.digest(facts)!=p.digest(w.read_facts(reader,value,include_reservation=False)):
            raise ValueError('Fresh reservation facts changed')
        probe=copy.deepcopy(value)
        probe.update(claim=None,receipt=None,next_action=None)
        preflight=w.observe(probe,facts)
        if preflight['reason']!='Single-owner claim missing; no next operation':
            raise ValueError('Reservation preflight stopped: '+preflight['reason'])
        pull=facts['pr'];waiting=[c for c in facts['issue_comments'] if c['id']==value['waiting_record']['comment_id']]
        if (pull['merged'] is not True or pull['head']['sha']!=value['reviewed_head_sha']
                or pull['merge_commit_sha']!=value['merge_sha'] or facts['main_sha']!=value['merge_sha']
                or facts.get('resume_authorization')!=value['authorization']
                or facts['policy'].get('resume_protocol')!=2 or facts['policy']['owner']!=value['owner']
                or len(waiting)!=1 or not author_matches(waiting[0].get('user'),value['owner'])
                or hashlib.sha256(waiting[0]['body'].encode()).hexdigest()!=value['waiting_record']['body_sha256']):
            raise ValueError('Fresh reservation scope/waiting/policy mismatch')
        journal=p.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else {}
        saved=acquire(api,value,args.capability_file.read_text(encoding='utf-8').strip(),journal,
                      lambda record:w.save_observation(args.state,record))
        w.save_observation(args.state,{**journal,'status':'ACQUIRED','reservation':saved})
        print(p.canonical(saved))
        return 0
    except (OSError,KeyError,TypeError,ValueError) as error:
        stopped=dict(status='STOPPED',stage='reservation acquisition',
                     reason=str(error) if isinstance(error,ValueError) else type(error).__name__,
                     next_owner='Work(root)',next_action='Read exact ref and current facts; never resend unknown writes',
                     retained=['private capability file','handoff','existing reservation if any'])
        # Keep durable attempted binding; a diagnostic must not erase it.
        if args.state.exists():
            prior=p.loads(args.state.read_text(encoding='utf-8'));stopped={**prior,'diagnostic':stopped}
        w.save_observation(args.state,stopped);print(p.canonical(stopped));return 1


if __name__=='__main__':raise SystemExit(main())
