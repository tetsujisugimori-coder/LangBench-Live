"""Synthetic inbox/ref/CI fixtures, never a live reservation or measurement."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import i01_management as m, startup_preparation as p, preparation_github as g
from tools import work_owner_resume as w, work_resume_claim as c
from tools.automation_dashboard import BOT, WORK, work_review, validate_policy_config
from tests.test_preparation_evidence import fixture as preparation_fixture, T0, T1
from tests.test_work_resume_claim import capability_fixture, RefAPI

ROOT=Path(__file__).resolve().parents[1]
ISSUE_URL='https://api.github.com/repos/'+m.REPOSITORY+'/issues/102'


def comment(ident,body,author=BOT):
    return dict(id=ident,body=body,user=copy.deepcopy(author),issue_url=ISSUE_URL,created_at=T0,updated_at=T0)


def fixture():
    value,owner,_=preparation_fixture('PRE_MERGE')
    value.update(issue=102,purpose=m.SCOPE[1],pr=103)
    owner.update(issue=102,purpose=m.SCOPE[1],input_digest=p.digest(value))
    for role in ('review','owner_resume'):
        owner[role]['settings']['trigger']['pr']=103
        if owner[role]['event']:owner[role]['event']['pr']=103
    policy=p.policy_entry(value)
    generated=p.generate(value,dict(schema_version=2,repository=m.REPOSITORY,issues={'102':policy}),owner_facts=owner)['github_record.md']
    record=g.block(generated,p.evidence_contract().REQUEST_START,p.REQUEST_END)
    base=comment(100,generated,policy['owner'])
    extension=copy.deepcopy(json.loads((ROOT/'.github/automation-dashboard.json').read_text(encoding='utf-8'))['issues']['102'])
    policy.update({k:extension[k] for k in ('i01_manager','manual_review')})
    policy['i01_manager'].update(base_comment_id=100,base_record_digest=m.record_digest(record))
    return policy,base,record


def reserve_fixture():
    policy,base,record=fixture();value,facts=capability_fixture()
    value.update(issue=102,purpose=m.SCOPE[1],pr=103)
    value['work']['automation_id']=record['input']['owner_resume_id']
    value['event']['pr']=103
    for key in ('claim','receipt','next_action','recheck'):value[key]=None
    request=m.build_request(record,handoff=value,request_id='1'*64)
    source=comment(101,m.encoded(m.REQUEST,request),policy['owner'])
    value=m.bound_handoff(request,source['id'])
    facts['policy']=policy
    facts['issue'].update(number=102,body='purpose: '+m.SCOPE[1])
    facts['pr'].update(number=103,body='Refs #102')
    review=p.loads(facts['pr_comments'][0]['body'].split('\n')[1]);review.update(issue=102,pr=103,automation_id=policy['work_automation_id'])
    facts['pr_comments'][0]['body']=m.encoded(WORK,review)
    facts['managed_actor_verified']=True
    facts['resume_authorization']=value['authorization']
    return policy,[base,source],record,request,value,facts


class API(RefAPI):
    def __init__(self,comments):super().__init__();self.comments=copy.deepcopy(comments);self.bound=None;self.token="synthetic";self.fail_journal=None;self.comment_posts=[]
    def bind(self,value):self.bound=copy.deepcopy(value)
    def pages(self,suffix,key=None):
        if suffix=='/issues/102/comments':return copy.deepcopy(self.comments)
        raise AssertionError(suffix)
    def get(self,path):
        if path.startswith('/issues/comments/'):
            return copy.deepcopy(next(x for x in self.comments if x['id']==int(path.rsplit('/',1)[1])))
        if path=='/pulls/103':return dict(number=103,head={'sha':'a'*40},base={'ref':'main','repo':{'full_name':m.REPOSITORY}})
        return super().get(path)
    def request(self,path,method,data):
        if '/issues/' in path:
            self.comment_posts.append((path,copy.deepcopy(data)))
            if method=='POST':
                saved=comment(max(x['id'] for x in self.comments)+1,data['body'])
                if self.fail_journal=='before':raise OSError('journal send unknown')
                self.comments.append(saved)
                if self.fail_journal=='after':raise OSError('journal accepted response lost')
                return copy.deepcopy(saved)
            target=next(x for x in self.comments if x['id']==int(path.rsplit('/',1)[1]));target['body']=data['body'];return copy.deepcopy(target)
        return super().request(path,method,data)


class ManagerTests(unittest.TestCase):
    def test_policy_scope_and_version_barrier(self):
        policy,_,_=fixture();m.validate_extensions(102,policy)
        for issue in (100,103):
            with self.assertRaises(ValueError):m.validate_extensions(issue,policy)
        config=dict(schema_version=2,repository=m.REPOSITORY,issues={'102':policy})
        validate_policy_config(config)
        policy['i01_manager']['base_record_digest']='bad'
        with self.assertRaises(ValueError):validate_policy_config(config)
    def test_actor_request_no_service_or_possession_claim(self):
        policy,comments,_,request,value,_=reserve_fixture()
        self.assertIsNone(value['work']['run_id']);self.assertEqual(value['work']['identity']['assurance'],'github_actor_not_service_run')
        m.authenticate_managed_handoff(value,comments,policy)
        with self.assertRaises(ValueError):c.verify_possession(value,'12'*32)
        self.assertEqual(m.inbox(comments,102,policy)[request['request_id']][0]['id'],101)
    def test_duplicate_identical_request_uses_first_transport_id(self):
        policy,comments,_,request,value,_=reserve_fixture()
        comments.append(comment(102,comments[-1]['body'],policy['owner']))
        self.assertEqual(len(m.inbox(comments,102,policy)),1)
        m.authenticate_managed_handoff(value,comments,policy)
        value['work']['identity']['authorization_comment_id']=102
        with self.assertRaises(ValueError):m.authenticate_managed_handoff(value,comments,policy)
    def test_duplicate_id_different_payload_rejected(self):
        policy,comments,_,request,_,_=reserve_fixture();r=copy.deepcopy(request);r['handoff']['event']['delivery_id']='different'
        comments.append(comment(102,m.encoded(m.REQUEST,r),policy['owner']))
        with self.assertRaises(ValueError):m.inbox(comments,102,policy)
    def test_edited_or_wrong_author_or_wrong_issue_request_rejected(self):
        for change in (lambda x:x.update(updated_at=T1),lambda x:x.update(user=BOT),lambda x:x.update(issue_url=ISSUE_URL.replace('102','100'))):
            policy,comments,_,_,_,_=reserve_fixture();change(comments[-1])
            with self.assertRaises(ValueError):m.inbox(comments,102,policy)
    def test_unbound_claimed_transport_and_other_issue_rejected(self):
        for field,value in [('authorization_comment_id',101),('scheme','capability_v1'),('assurance','bearer_possession_not_service_run')]:
            policy,comments,_,r,_,_=reserve_fixture();r['handoff']['work']['identity'][field]=value
            comments[-1]['body']=m.encoded(m.REQUEST,r)
            with self.assertRaises(ValueError):m.inbox(comments,102,policy)
    def test_pre_send_journal_and_crash_reload_no_repeat(self):
        _,comments,_,r,v,_=reserve_fixture();api=API(comments)
        saved=m.attempt_reservation(api,r,v,comments)
        self.assertEqual(len(api.posts),2)
        journals=m.bot_records(api.comments,m.JOURNAL,102)
        self.assertEqual([x[1]['stage'] for x in journals],['commit','ref','acquired'])
        self.assertEqual(m.attempt_reservation(api,r,v,api.comments),saved)
        self.assertEqual(len(api.posts),2)
    def test_ambiguous_commit_send_or_pre_ref_journal_never_retries(self):
        for failure in ('commit','ref_journal'):
            _,comments,_,r,v,_=reserve_fixture();api=API(comments);original=api.request
            def send(path,method,data):
                if failure=='commit' and path.endswith('/git/commits'):
                    original(path,method,data);raise OSError('lost commit response')
                if failure=='ref_journal' and (m.envelope(data.get('body'),m.JOURNAL) or {}).get('stage')=='ref':
                    original(path,method,data);raise OSError('lost ref journal response')
                return original(path,method,data)
            api.request=send
            with self.assertRaises((OSError,ValueError)):m.attempt_reservation(api,r,v,comments)
            count=len(api.posts)
            with self.assertRaises((KeyError,ValueError)):m.attempt_reservation(api,r,v,api.comments)
            self.assertEqual(len(api.posts),count)
    def test_journal_publication_unknown_prevents_git_send(self):
        for state in ('before','after'):
            _,comments,_,r,v,_=reserve_fixture();api=API(comments);api.fail_journal=state
            with self.assertRaises(OSError):m.attempt_reservation(api,r,v,comments)
            self.assertEqual(api.posts,[])
    def test_ref_response_lost_is_reconciled_and_absence_is_not_resent(self):
        for fail in ('before','after'):
            _,comments,_,r,v,_=reserve_fixture();api=API(comments);api.fail=fail
            if fail=='before':
                with self.assertRaises(KeyError):m.attempt_reservation(api,r,v,comments)
                with self.assertRaises(KeyError):m.attempt_reservation(api,r,v,api.comments)
            else:m.attempt_reservation(api,r,v,comments);m.attempt_reservation(api,r,v,api.comments)
            self.assertEqual(len(api.posts),2)
    def test_different_request_fenced_by_ambiguous_operation_journal(self):
        _,comments,_,r,v,_=reserve_fixture();api=API(comments);api.fail='before'
        with self.assertRaises(KeyError):m.attempt_reservation(api,r,v,comments)
        r=copy.deepcopy(r);r['request_id']='2'*64
        with self.assertRaises(ValueError):m.attempt_reservation(api,r,v,api.comments)
        self.assertEqual(len(api.posts),2)
    def test_duplicate_or_edited_journal_rejected(self):
        for duplicate in (True,False):
            _,comments,_,r,v,_=reserve_fixture();api=API(comments);m.attempt_reservation(api,r,v,comments)
            if duplicate:api.comments.append(comment(900,api.comments[-1]['body']))
            else:api.comments[-1]['updated_at']=T1
            with self.assertRaises(ValueError):m.attempt_reservation(api,r,v,api.comments)
            self.assertEqual(len(api.posts),2)
    def test_inbox_preflight_twice_and_actual_merge_missing_sends_zero(self):
        policy,comments,_,_,_,facts=reserve_fixture();api=API(comments)
        with patch.object(w,'read_facts',return_value=facts) as read:
            self.assertEqual(m.process_inbox(api,102,policy),'RECONCILED 1');self.assertEqual(read.call_count,2)
        facts['pr']['merged']=False
        policy,comments,_,_,_,_=reserve_fixture();api=API(comments)
        with patch.object(w,'read_facts',return_value=facts):
            with self.assertRaises(ValueError):m.process_inbox(api,102,policy)
        self.assertEqual(api.posts,[])
    def test_public_response_read_builds_exact_claim_without_writes(self):
        policy,comments,_,r,value,_=reserve_fixture();api=API(comments)
        self.assertEqual(m.read_response(api,101,policy)['status'],'PENDING')
        m.attempt_reservation(api,r,value,comments)
        count=(len(api.posts),len(api.comment_posts))
        response=m.read_response(api,101,policy)
        self.assertEqual(response['status'],'ACQUIRED')
        self.assertEqual(c.binding(response['handoff']),c.binding(value))
        self.assertEqual(response['handoff']['claim']['ref'],c.reservation_ref(value))
        self.assertEqual(count,(len(api.posts),len(api.comment_posts)))
    def test_cli_request_generation_preserves_saved_nonce_without_network(self):
        policy,_,record,r,value,_=reserve_fixture()
        # Generator takes a local unclaimed v2 handoff, not a claimed response.
        value['work']['identity']['authorization_comment_id']=None
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);config=directory/'config.json';inputfile=directory/'input.json';handoff=directory/'handoff.json';output=directory/'request.md'
            config.write_text(p.canonical(dict(schema_version=2,repository=m.REPOSITORY,issues={'102':policy})),encoding='utf-8')
            inputfile.write_text(p.canonical(record),encoding='utf-8');handoff.write_text(p.canonical(value),encoding='utf-8')
            command=[sys.executable,'-B',str(ROOT/'tools/i01_management.py'),'--config',str(config),'--preparation-record',str(inputfile),'--reserve-handoff',str(handoff),'--output',str(output)]
            first=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            saved=output.read_bytes();request=m.envelope(saved.decode(),m.REQUEST)
            self.assertIsNone(request['handoff']['work']['identity']['authorization_comment_id'])
            second=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0);self.assertEqual(output.read_bytes(),saved)
    def test_fresh_managed_handoff_reader_authenticates_current_transport(self):
        import base64
        policy,comments,_,_,value,facts=reserve_fixture()
        # Reuse one valid preparation record and bind the synthetic waiting bytes.
        current=g.authenticated_request(comments[0],102,policy)
        waiting=current['owner_facts']['waiting_record']
        value['waiting_record']={k:waiting[k] for k in ('comment_id','body_sha256')}
        value['authorization']=dict(kind=waiting['allowed_action'],effect='read_only',authorization_ref=waiting['authorization_ref'])
        request=m.build_request(current,handoff=value,request_id='4'*64)
        comments[-1]=comment(101,m.encoded(m.REQUEST,request),policy['owner']);value=m.bound_handoff(request,101)
        facts=copy.deepcopy(facts);facts['issue_comments']=comments;facts['dashboard_comment_id']=None
        class Reader:
            artifacts={}
            def get(self,suffix):
                if suffix=='/branches/main':return {'commit':{'sha':value['merge_sha']}}
                if suffix.startswith('/contents/'):return {'content':base64.b64encode(p.canonical(dict(schema_version=2,repository=m.REPOSITORY,issues={'102':policy})).encode()).decode()}
                if suffix=='/issues/102':return facts['issue']
                raise AssertionError(suffix)
        with patch('tools.work_owner_resume.collect',return_value=(None,facts)):
            observed=w.read_facts(Reader(),value,include_reservation=False)
            self.assertTrue(observed['managed_actor_verified'])
            comments[-1]['updated_at']=T1
            with self.assertRaises(ValueError):w.read_facts(Reader(),value,include_reservation=False)
    def test_production_transport_rejects_patch_and_arbitrary_git_or_comment(self):
        _,_,_,_,value,_=reserve_fixture();api=m.ManagerGitHub('synthetic');api.bind(value)
        with patch.object(api,'_send_request',side_effect=AssertionError('must not send')):
            for suffix,method,data in [('/issues/102/comments','POST',{'body':'ordinary prose'}),('/issues/100/comments','POST',{'body':m.encoded(m.JOURNAL,{})}),('/git/refs','PATCH',{}),('/issues/comments/100','PATCH',{})]:
                with self.assertRaises(ValueError):api.request(api.root+suffix,method,data)
    def test_missing_token_before_journal(self):
        _,comments,_,r,v,_=reserve_fixture();api=API(comments)
        api.check_write_ready=lambda:(_ for _ in ()).throw(ValueError('missing token'))
        with self.assertRaises(ValueError):m.attempt_reservation(api,r,v,comments)
        self.assertEqual(api.comment_posts,[]);self.assertEqual(api.posts,[])


class AmendmentTests(unittest.TestCase):
    def proposal(self):
        policy,base,current=fixture();candidate=copy.deepcopy(current)
        candidate['input']['input_version']+=1;candidate['input_version']+=1
        candidate['input_history'].append(current['input']);candidate['input_digest']=p.digest(candidate['input'])
        candidate['owner_facts'].update(input_version=candidate['input_version'],input_digest=candidate['input_digest'],observed_at=T1)
        request=m.build_request(current,update=candidate,request_id='2'*64)
        source=comment(101,m.encoded(m.REQUEST,request),policy['owner'])
        return policy,base,current,candidate,request,source
    def test_generator_preserves_existing_extensions_instead_of_reregistering(self):
        policy,_,_,candidate,_,_=self.proposal()
        config=dict(schema_version=2,repository=m.REPOSITORY,issues={'102':policy})
        generated=p.generate(candidate['input'],config,owner_facts=candidate['owner_facts'])
        self.assertEqual(p.loads(generated['policy_diff.json'])['issues'],{})
        self.assertIn('i01_manager',config['issues']['102'])
    def test_management_update_keeps_one_immutable_base_and_writer_twice(self):
        policy,base,current,candidate,request,source=self.proposal();api=API([base,source]);before=base['body']
        self.assertEqual(m.process_inbox(api,102,policy),'RECONCILED 1')
        self.assertEqual(m.process_inbox(api,102,policy),'RECONCILED 0')
        self.assertEqual(api.comments[0]['body'],before)
        self.assertEqual(sum(g.request_version(x['body']) is not None for x in api.comments),1)
        self.assertEqual(g.select_preparation(api.comments,102,policy)[1],candidate)
        fake_facts={'input_digest':candidate['input_digest'],'fetch_error':True}
        with patch.object(g,'current_preparation_facts',return_value=fake_facts):
            self.assertEqual(g.reconcile_preparation(api,102,policy,T1),'UPDATED')
            self.assertEqual(g.reconcile_preparation(api,102,policy,T1),'NO_OP')
        self.assertEqual(api.comments[0]['body'],before)
        self.assertEqual(g.select_preparation(api.comments,102,policy)[2]['input_version'],2)
    def test_base_change_or_multiple_base_rejected(self):
        policy,base,current,_,_,_=self.proposal()
        changed=copy.deepcopy(current);changed['owner_facts']['observed_at']=T1
        base['body']=p.evidence_contract().REQUEST_START+p.canonical(changed)+p.REQUEST_END
        with self.assertRaises(ValueError):g.select_preparation([base],102,policy)
        policy,base,_,_,_,_=self.proposal()
        with self.assertRaises(ValueError):g.select_preparation([base,comment(102,base['body'],policy['owner'])],102,policy)
    def test_stale_version_scope_and_removed_history_rejected(self):
        for mutate in (lambda r:r.update(expected_input_digest='f'*64),lambda r:r['record']['input_history'].clear(),lambda r:r['record']['input'].update(owner_resume_id='f'*32)):
            policy,_,current,_,request,_=self.proposal();mutate(request)
            with self.assertRaises(ValueError):m.validate_update(current,request,102,policy)
    def test_competing_same_version_updates_send_nothing(self):
        policy,base,_,_,r,source=self.proposal();second=copy.deepcopy(r);second['request_id']='3'*64
        api=API([base,source,comment(102,m.encoded(m.REQUEST,second),policy['owner'])])
        with self.assertRaises(ValueError):m.process_inbox(api,102,policy)
        self.assertEqual(api.comment_posts,[])
    def test_lost_amendment_response_recovered_without_duplicate(self):
        policy,base,_,candidate,_,source=self.proposal();api=API([base,source]);api.fail_journal='after'
        with self.assertRaises(OSError):m.process_inbox(api,102,policy)
        api.fail_journal=None
        self.assertEqual(m.process_inbox(api,102,policy),'RECONCILED 0')
        self.assertEqual(g.select_preparation(api.comments,102,policy)[1],candidate)
        self.assertEqual(len(api.comment_posts),1)
    def test_branch_edited_amendment_and_untrusted_snapshot_rejected(self):
        for mode in ('branch','edit','snapshot'):
            policy,base,_,_,_,source=self.proposal();api=API([base,source]);m.process_inbox(api,102,policy)
            if mode=='branch':api.comments.append(comment(999,api.comments[-1]['body']))
            if mode=='edit':api.comments[-1]['updated_at']=T1
            if mode=='snapshot':api.comments.append(comment(999,m.SNAPSHOT+'\n',policy['owner']))
            with self.assertRaises(ValueError):g.select_preparation(api.comments,102,policy)
    def test_failed_public_collection_retains_new_negative_owner_observation(self):
        policy,base,_,candidate,request,source=self.proposal()
        candidate['owner_facts']['owner_resume']['settings']['enabled']=False
        request['record']=candidate;source['body']=m.encoded(m.REQUEST,request)
        api=API([base,source]);m.process_inbox(api,102,policy)
        with patch.object(g,'current_preparation_facts',side_effect=OSError('read failed')):
            with self.assertRaises(ValueError):g.reconcile_preparation(api,102,policy,T1)
        _,_,saved=g.select_preparation(api.comments,102,policy)
        self.assertFalse(saved['state']['owner_watermarks']['owner_resume']['record']['settings']['enabled'])
        self.assertEqual(saved['state']['status'],'WAITING')
    def test_snapshot_creation_crash_can_be_reconciled(self):
        policy,base,record=fixture();api=API([base,comment(102,m.SNAPSHOT+'\n')])
        with patch.object(g,'current_preparation_facts',return_value={'input_digest':record['input_digest'],'fetch_error':True}):
            self.assertEqual(g.reconcile_preparation(api,102,policy,T0),'UPDATED')
        self.assertEqual(len(api.comment_posts),1)


class ManualReviewTests(unittest.TestCase):
    def fixture(self):
        policy,_,_=fixture();value=dict(schema_version=1,kind='manual_work_review',repository=m.REPOSITORY,issue=102,pr=103,head_sha='a'*40,
            actor=policy['manual_review']['actor'],delegation_ref=policy['manual_review']['delegation_ref'],verdict='PASS',blockers=[],active_blocker=None,follow_up=[],follow_up_recorded=True,conditions={})
        review=dict(id=555,commit_id='a'*40,state='COMMENTED',submitted_at=T0,user=policy['work_author'],body=m.encoded(m.REVIEW,value))
        return policy,value,review
    def test_same_head_structured_review_retains_manual_provenance(self):
        policy,_,review=self.fixture();result,_=work_review([],102,103,'a'*40,policy,[review])
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['route'],'manual_handoff')
        self.assertEqual(result['github_review_state'],'COMMENTED');self.assertFalse(result['service_run_verified'])
    def test_old_head_prose_other_author_and_root_comment_not_accepted(self):
        policy,_,review=self.fixture();self.assertEqual(work_review([],102,103,'b'*40,policy,[review])[0]['status'],'STALE')
        for mutate in (lambda r:r.update(body='PASS'),lambda r:r.update(user=BOT)):
            r=copy.deepcopy(review);mutate(r)
            self.assertEqual(work_review([],102,103,'a'*40,policy,[r])[0]['status'],'PENDING')
        self.assertEqual(work_review([review],102,103,'a'*40,policy)[0]['status'],'PENDING')
    def test_dismissed_bad_delegation_commit_mismatch_and_changes_requested_block(self):
        for mutate in (lambda r:r.update(state='DISMISSED'),lambda r:r.update(commit_id='b'*40),lambda r:r.update(state='CHANGES_REQUESTED'),lambda r:r.update(body=r['body'].replace('/root/pr103_independent_review','Work(root)'))):
            policy,_,review=self.fixture();mutate(review)
            self.assertEqual(work_review([],102,103,'a'*40,policy,[review])[0]['status'],'ERROR')
    def test_newer_negative_review_supersedes_pass(self):
        policy,value,review=self.fixture();value.update(verdict='BLOCKED',blockers=['synthetic blocker'])
        newer=dict(review,id=556,submitted_at=T1,body=m.encoded(m.REVIEW,value))
        self.assertEqual(work_review([],102,103,'a'*40,policy,[review,newer])[0]['status'],'BLOCKED')
    def test_managed_owner_uses_same_review_evaluator_and_requires_actor_readback(self):
        policy,comments,_,_,value,facts=reserve_fixture();manual_policy,_,review=self.fixture()
        facts['pr_comments']=[];facts['reviews']=[review]
        facts['managed_actor_verified']=False
        self.assertIn('freshly authenticated',w.observe(value,facts)['reason'])
        facts['managed_actor_verified']=True
        self.assertEqual(w.observe(value,facts)['reason'],'Single-owner claim missing; no next operation')
    def test_original_automation_and_other_issue_unchanged(self):
        value,facts=capability_fixture()
        self.assertEqual(w.observe(value,facts)['status'],'OBSERVED')
        policy,_,review=self.fixture()
        with self.assertRaises(ValueError):m.manual_review_records([review],100,103,policy)


if __name__=='__main__':unittest.main()
