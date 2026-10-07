"""Issue #88 synthetic acceptance tests. No real Work, dispatch or measurement."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import startup_preparation as p
from tools.preparation_github import (reconcile_preparation, PreparationConflict,
                                     PreparationWriteUnknown, snapshot, read_facts)
from tools.automation_dashboard import evaluate, initial_state, render, parse_state, RECEIPT, dedup_key
from tests.test_automation_dashboard import ROOT, NOW, HEAD, record, fixtures


def input_fixture():
    return json.loads((ROOT / 'docs/startup-preparation-input.json').read_text())


def facts_fixture(v):
    return {'input_digest': p.digest(v), 'issue': {'number':88, 'repository':p.REPOSITORY,
        'purpose':p.PURPOSE,'owner':v['owner']}, 'review': {'id':v['work_automation_id'],
        'enabled':True,'event_verified':True}, 'main_policy':p.policy_entry(v), 'main_sha':HEAD,
        'dashboard':{'repository':p.REPOSITORY,'issue':88,'purpose':p.PURPOSE,'comment_id':123},
        'publication':{'available':True,'route':'synthetic'}}


def owner_facts(v, available=True):
    return {'schema_version':1, 'repository':v['repository'], 'issue':v['issue'],
        'purpose':v['purpose'], 'owner':v['owner'], 'input_version':v['input_version'],
        'input_digest':p.digest(v), 'start_main_sha':v['start_main_sha'], 'observed_at':NOW,
        'review':{'available':available, 'id':v['work_automation_id'] if available else None,
            'enabled':True if available else None, 'target_event':'pull_request' if available else None,
            'actual_event':'pull_request' if available else None, 'event_verified':True if available else None,
            'evidence_ref':'work://synthetic/review', 'confirmed_by':v['actors']['dispatch']},
        'publication':{'available':available, 'publisher':v['actors']['publication'],
            'primary_route':'github-connector' if available else None,
            'recovery_route':'task-artifact' if available else None,
            'evidence_ref':'work://synthetic/publication'}}


class PreparationAPI:
    def __init__(self, value):
        self.root = '/repos/' + p.REPOSITORY
        self.value = value
        self.config = {'schema_version':1,'repository':p.REPOSITORY,'issues':{str(value['issue']):p.policy_entry(value)}}
        body = p.generate(value, self.config)['github_record.md']
        self.comment = {'id':100,'body':'Human before\n'+body+'\nHuman after','user':value['owner']}
        self.writes = []
        self.fail = None
        self.hook = None
        self.pull = None
        self.extra = []
        self.issue = {'number':value['issue'],'user':value['owner'],'body':'purpose: '+value['purpose']}
        self.main_sha = HEAD
    def pages(self, suffix, key=None):
        if suffix.startswith(f"/issues/{self.value['issue']}/comments"):
            return copy.deepcopy([self.comment] + self.extra)
        if suffix.startswith('/pulls?'): return [copy.deepcopy(self.pull)] if self.pull else []
        raise AssertionError(suffix)
    def get(self, suffix):
        if self.hook: self.hook(suffix)
        if suffix == f"/issues/{self.value['issue']}": return copy.deepcopy(self.issue)
        if suffix == '/issues/comments/100': return copy.deepcopy(self.comment)
        if suffix == '/git/ref/heads/main': return {'object':{'sha':self.main_sha}}
        if suffix.startswith('/contents/'):
            return {'encoding':'base64','content':base64.b64encode(json.dumps(self.config).encode()).decode()}
        if suffix == '/pulls/89': return copy.deepcopy(self.pull)
        raise AssertionError(suffix)
    def request(self, path, method, data):
        self.writes.append((path,method,copy.deepcopy(data)))
        self.comment['body'] = data['body']
        if self.fail: raise self.fail
        return copy.deepcopy(self.comment)


class InputGeneration(unittest.TestCase):
    def setUp(self): self.v=input_fixture()
    def test_deterministic_all_input_output_and_null_ids(self):
        config={'schema_version':1,'repository':p.REPOSITORY,'issues':{}}
        generated=p.generate(self.v,config)
        self.assertEqual(generated,p.generate(copy.deepcopy(self.v),config))
        self.assertEqual({'issue_body.md','review_registration.md','policy_diff.json','preparation.json','summary.md','github_record.md'},set(generated))
        for field in ('repository','purpose','start_main_sha','specification'):
            self.assertIn(self.v[field],generated['issue_body.md'])
        state=p.loads(generated['preparation.json'])
        self.assertTrue(all(s['evidence'] is None for s in state['stages'].values()))
        policy=p.loads(generated['policy_diff.json'])['issues']['88']
        self.assertIsNone(policy['initial_dispatch']); self.assertIsNone(policy['dashboard_comment_id'])
        self.assertIn('期限保証不能',generated['summary.md'])
        self.assertIn('機械Merge Gate未認定',generated['summary.md'])
    def test_missing_requirement_reason_actor_not_filled(self):
        for field in ('requirements','requirement_reasons','actors'):
            v=copy.deepcopy(self.v); v[field].pop(next(iter(v[field])))
            with self.assertRaises(ValueError): p.validate_input(v)
    def test_scope_schema_and_identity_fail_closed(self):
        for key,val in [('issue',0),('purpose','invalid purpose'),('repository','other/repo'),('schema_version',True),
                        ('start_main_sha','short'),('input_version',0),('owner',{'login':'bad'})]:
            v=copy.deepcopy(self.v); v[key]=val
            with self.assertRaises(ValueError): p.validate_input(v)
    def test_unknown_review_id_is_null_and_no_policy(self):
        self.v['work_automation_id']=None
        result=p.generate(self.v,{'schema_version':1,'repository':p.REPOSITORY,'issues':{}})
        self.assertEqual('null\n',result['policy_diff.json'])
        self.assertIn('automation_id: null',result['review_registration.md'])
    def test_existing_policy_conflict_and_no_mutation(self):
        config={'schema_version':1,'repository':p.REPOSITORY,'issues':{'88':p.policy_entry(self.v)}}
        before=copy.deepcopy(config)
        self.assertEqual({},p.policy_diff(self.v,config)['issues']); self.assertEqual(before,config)
        config['issues']['88']['purpose']='other'
        with self.assertRaises(ValueError): p.policy_diff(self.v,config)
    def test_duplicate_keys_nan_rejected(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}'):
            with self.assertRaises(ValueError): p.loads(text)
    def test_real_policy_80_85_identical_and_initial_null(self):
        config=json.loads((ROOT/'.github/automation-dashboard.json').read_text())
        old=json.loads(subprocess.check_output(['git','show','5eda8bbf5be8433b2f3909c4e7a17a0cd13b9aef:.github/automation-dashboard.json'],cwd=ROOT,text=True))
        for issue in ('80','85'): self.assertEqual(old['issues'][issue],config['issues'][issue])
        self.assertEqual(p.policy_entry(self.v),config['issues']['88'])
        self.assertIsNone(config['issues']['88']['initial_dispatch'])


class StateResume(unittest.TestCase):
    def setUp(self): self.v=input_fixture(); self.state=p.new_state(self.v); self.facts=facts_fixture(self.v)
    def test_atomic_roundtrip_and_corruption_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            p.atomic_save(path,self.state)
            self.assertEqual(self.state,p.validate_state(p.loads(path.read_text())))
            path.write_text('{broken')
            with self.assertRaises(ValueError): p.atomic_save(path,self.state)
            self.assertEqual('{broken',path.read_text())
    def test_replace_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'; p.atomic_save(path,self.state); original=path.read_bytes()
            with patch('tools.startup_preparation.os.replace',side_effect=OSError('synthetic')):
                with self.assertRaises(OSError): p.atomic_save(path,self.state)
            self.assertEqual(original,path.read_bytes()); self.assertEqual([path],list(path.parent.iterdir()))
    def test_resume_complete_distinct_gate_and_noop(self):
        state=p.resume(self.state,self.facts,NOW)
        self.assertEqual('PREPARATION_COMPLETE',state['status'])
        self.assertNotIn('merge_gate',state)
        self.assertEqual(state,p.resume(state,self.facts,'2026-10-08T00:00:00Z'))
        self.assertFalse(state['shared_persistence'])
    def test_enabled_armed_not_event_or_implementation(self):
        self.facts['review']['event_verified']=False
        state=p.resume(self.state,self.facts,NOW)
        self.assertEqual('WAITING',state['stages']['review']['status'])
        self.assertNotEqual('PREPARATION_COMPLETE',state['status'])
        self.assertIn('implementation',p.summary(state))
    def test_merged_pr_still_not_main_application(self):
        self.facts.pop('main_policy'); self.facts['policy_pr']={'number':89,'merged':True}
        state=p.resume(self.state,self.facts,NOW)
        self.assertEqual('WAITING',state['stages']['policy']['status'])
        self.assertIn('readback',state['stages']['policy']['waiting_reason'])
    def test_changes_invalidate_only_dependencies(self):
        complete=p.resume(self.state,self.facts,NOW)
        for key,change in [('start_main_sha','c'*40),('owner',{'login':'other','id':1,'type':'User'}),
                           ('actors',{**self.v['actors'],'publication':'other'})]:
            v=copy.deepcopy(self.v); v.update({key:change,'input_version':2})
            state=p.rebase(complete,v)
            affected=[k for k,deps in p.DEPENDENCIES.items() if key in deps]
            for stage in p.STAGES:
                self.assertEqual('INVALIDATED' if stage in affected else 'CONFIRMED',state['stages'][stage]['status'])
        with self.assertRaises(ValueError): p.rebase(complete,{**self.v,'start_main_sha':'c'*40})
    def test_unknown_send_crash_restart_dedup_and_reconcile(self):
        state=p.mark_unknown(self.state,'policy_pr')
        loaded=p.loads(p.canonical(state))
        with self.assertRaises(ValueError): p.mark_unknown(loaded,'policy_pr')
        key=p.operation_key(self.v,'policy_pr')
        state=p.resume(loaded,self.facts,NOW)
        self.assertEqual('UNKNOWN',state['operations'][key]['status'])
        self.facts['operations']={key:{'id':89,'input_digest':p.digest(self.v)}}
        state=p.resume(state,self.facts,NOW)
        self.assertEqual(89,state['operations'][key]['external_id'])
        with self.assertRaises(ValueError): p.mark_unknown(state,'policy_pr')
    def test_unknown_operation_retained_on_new_input(self):
        state=p.mark_unknown(self.state,'implementation_task')
        v={**self.v,'input_version':2,'start_main_sha':'c'*40}
        revised=p.rebase(state,v)
        self.assertEqual(state['operations'],revised['operations'])
        current=p.resume(revised,{**facts_fixture(v),'operations':{}},NOW)
        self.assertEqual('WAITING',current['status'])
    def test_external_mismatch_missing_sha_failures_non_success(self):
        for field in ('owner','purpose','number','repository'):
            f=copy.deepcopy(self.facts); f['issue'][field]='wrong'
            with self.assertRaises(ValueError): p.resume(self.state,f,NOW)
        self.facts.pop('main_sha')
        with self.assertRaises(ValueError): p.resume(self.state,self.facts,NOW)
    def test_fresh_missing_evidence_clears_cached_confirmation(self):
        state=p.resume(self.state,self.facts,NOW)
        result=p.resume(state,{'input_digest':p.digest(self.v)},NOW)
        self.assertEqual('WAITING',result['status'])
        self.assertIsNone(result['stages']['review']['evidence'])

    def test_next_owner_follows_pending_authority(self):
        cases = [
            ({'review':None}, self.v['actors']['dispatch'], 'review'),
            ({'dashboard':None}, self.v['actors']['dispatch'], 'dashboard'),
            ({'main_policy':None, 'policy_pr':{'number':89,'merged':False}}, 'human merge owner', 'Human merge'),
            ({'main_policy':None}, self.v['actors']['dispatch'], 'publish'),
            ({'publication':None}, self.v['actors']['publication'], 'publication'),
        ]
        for changes, owner, action in cases:
            facts=copy.deepcopy(self.facts)
            for key,value in changes.items():
                if value is None: facts.pop(key,None)
                else: facts[key]=value
            state=p.resume(self.state,facts,NOW)
            self.assertEqual(owner,state['next_owner']); self.assertIn(action,state['next_action'])

    def test_cli_read_failure_saves_stopped_not_cached_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); input_path=base/'input.json'; state_path=base/'state.json'
            input_path.write_text(p.canonical(self.v)); p.atomic_save(state_path,p.resume(self.state,self.facts,NOW))
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(state_path),
                                  '--output',str(base/'generated'),'--github-read']), \
                 patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.preparation_github.read_facts',side_effect=OSError('synthetic offline')), \
                 patch('builtins.print'):
                with self.assertRaises(OSError): p.main()
            saved=p.validate_state(p.loads(state_path.read_text()))
            self.assertEqual('STOPPED',saved['status'])
            self.assertIn('no retransmission',saved['next_action'])

    def test_cli_github_read_reconciles_unique_policy_pr_without_write(self):
        state=p.mark_unknown(self.state,'policy_pr'); key=p.operation_key(self.v,'policy_pr')
        api=PreparationAPI(self.v)
        api.pull={'number':89,'body':'Refs #88\n','base':{'ref':'main','repo':{'full_name':p.REPOSITORY}},
                  'head':{'sha':HEAD},'merged':False}
        api.config['issues']={}
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); input_path=base/'input.json'; state_path=base/'state.json'
            input_path.write_text(p.canonical(self.v)); p.atomic_save(state_path,state)
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(state_path),
                                   '--output',str(base/'generated'),'--github-read']), \
                 patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.update_automation_dashboard.GitHub',return_value=api), patch('builtins.print'):
                self.assertEqual(0,p.main())
            saved=p.validate_state(p.loads(state_path.read_text()))
            self.assertEqual('CONFIRMED',saved['operations'][key]['status'])
            self.assertEqual(89,saved['operations'][key]['external_id']); self.assertEqual([],api.writes)


class GenericTargets(unittest.TestCase):
    def test_other_synthetic_issue_purpose_generate_save_resume_and_shared_record(self):
        for issue,purpose in ((101,'synthetic-feature'),(202,'synthetic-preparation-2')):
            value={**input_fixture(),'issue':issue,'purpose':purpose,
                   'owner':{'login':'synthetic-owner','id':42,'type':'User'}}
            api=PreparationAPI(value); policy=p.policy_entry(value)
            generated=p.generate(value,api.config)
            self.assertIn(f'Issue #{issue} / {purpose}',generated['summary.md'])
            state=p.mark_unknown(p.new_state(value),'policy_pr')
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'state.json'; p.atomic_save(path,state)
                restored=p.validate_state(p.loads(path.read_text()))
                observed=facts_fixture(value); observed['issue'].update(number=issue,purpose=purpose)
                observed['dashboard'].update(issue=issue,purpose=purpose)
                resumed=p.resume(restored,observed,NOW)
                self.assertEqual('UNKNOWN',next(iter(resumed['operations'].values()))['status'])
            self.assertEqual('UPDATED',reconcile_preparation(api,issue,policy,NOW))
            self.assertEqual(issue,snapshot(api.comment['body'])['state']['input']['issue'])
            self.assertEqual('NO_OP',reconcile_preparation(api,issue,policy,NOW))
            for field,wrong in (('issue',issue+1),('purpose','wrong-purpose')):
                other=copy.deepcopy(value); other[field]=wrong
                request=p.generate(other,{'schema_version':1,'repository':p.REPOSITORY,'issues':{}})['github_record.md']
                api.comment['body']=request
                with self.assertRaises(ValueError): reconcile_preparation(api,issue,policy,NOW)
    def test_issue_null_then_actual_id_added_and_evidence_invalidated(self):
        value={**input_fixture(),'issue':None,'purpose':'synthetic-uncreated'}
        generated=p.generate(value,{'schema_version':1,'repository':p.REPOSITORY,'issues':{}})
        self.assertEqual('null\n',generated['policy_diff.json'])
        self.assertIsNone(p.loads(generated['preparation.json'])['input']['issue'])
        state=p.mark_unknown(p.new_state(value),'issue')
        self.assertIn(':issuenull:',next(iter(state['operations'])))
        updated={**value,'issue':303,'input_version':2}
        revised=p.rebase(state,updated)
        self.assertEqual('INVALIDATED',revised['stages']['issue']['status'])
        self.assertEqual(state['operations'],revised['operations'])
        with self.assertRaises(ValueError): p.mark_unknown(revised,'issue')
        facts=facts_fixture(updated); facts['issue'].update(number=303,purpose=updated['purpose'])
        facts['dashboard'].update(issue=303,purpose=updated['purpose'])
        facts['operations']={next(iter(state['operations'])):{'id':303,'input_digest':p.digest(value)}}
        self.assertEqual('PREPARATION_COMPLETE',p.resume(revised,facts,NOW)['status'])
    def test_null_issue_public_reader_does_not_invent_or_fetch_issue(self):
        value={**input_fixture(),'issue':None}
        api=PreparationAPI(value)
        facts=read_facts(api,value)
        self.assertNotIn('issue',facts); self.assertNotIn('main_policy',facts)
        self.assertEqual('WAITING',p.resume(p.new_state(value),facts,NOW)['status'])
    def test_local_lock_and_changed_sha_unknown_resend_rejected(self):
        state=p.mark_unknown(p.new_state(input_fixture()),'implementation_task')
        value={**state['input'],'input_version':2,'start_main_sha':'c'*40}
        with self.assertRaises(ValueError): p.mark_unknown(p.rebase(state,value),'implementation_task')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            with p.state_lock(path):
                with self.assertRaises(ValueError):
                    with p.state_lock(path): pass
            self.assertFalse(path.with_name('state.json.lock').exists())


class GithubTransport(unittest.TestCase):
    def setUp(self): self.v=input_fixture(); self.api=PreparationAPI(self.v); self.policy=p.policy_entry(self.v)
    def update(self): return reconcile_preparation(self.api,88,self.policy,NOW)
    def test_same_comment_human_and_unrelated_receipt_preserved_noop(self):
        original=self.api.comment['body']; self.api.extra=[record(RECEIPT,{'synthetic':'unchanged'})]
        receipt=copy.deepcopy(self.api.extra)
        self.assertEqual('UPDATED',self.update())
        self.assertTrue(self.api.comment['body'].startswith(original))
        self.assertEqual(receipt,self.api.extra)
        self.assertEqual('NO_OP',reconcile_preparation(self.api,88,self.policy,'2026-10-08T00:00:00Z'))
        self.assertEqual(1,len(self.api.writes))
        self.api.comment['body']+='\nNew human note'
        self.assertEqual('NO_OP',self.update())
        self.assertIn('New human note',self.api.comment['body'])
    def test_fake_api_facts_no_work_or_publication_claim(self):
        facts=read_facts(self.api,self.v)
        self.assertNotIn('review',facts); self.assertNotIn('publication',facts)
        self.update(); state=snapshot(self.api.comment['body'])['state']
        self.assertEqual('WAITING',state['status']); self.assertTrue(state['shared_persistence'])
    def test_owner_observations_flow_cli_record_writer_resume_and_noop(self):
        observed=owner_facts(self.v)
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); input_path=base/'input.json'; facts_path=base/'owner.json'
            input_path.write_text(p.canonical(self.v)); facts_path.write_text(p.canonical(observed))
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(base/'state.json'),
                                   '--output',str(base/'generated'),'--owner-facts',str(facts_path)]), \
                 patch('builtins.print'):
                self.assertEqual(0,p.main())
            self.api.comment['body']=(base/'generated/github_record.md').read_text()
        self.assertEqual('UPDATED',self.update())
        state=snapshot(self.api.comment['body'])['state']
        self.assertEqual('CONFIRMED',state['stages']['review']['status'])
        self.assertEqual('CONFIRMED',state['stages']['publication']['status'])
        self.assertEqual(NOW,state['stages']['review']['evidence']['owner_observed_at'])
        self.assertNotIn(RECEIPT,self.api.comment['body']); self.assertEqual('NO_OP',self.update())
        unavailable=owner_facts(self.v,False)
        local=p.resume(p.new_state(self.v),{'input_digest':p.digest(self.v),
                       'review':unavailable['review'],'publication':unavailable['publication']},NOW)
        self.assertEqual('UNKNOWN',local['stages']['review']['status'])
        self.assertNotEqual(local['stages']['review']['status'],p.new_state(self.v)['stages']['review']['status'])
    def test_wrong_author_issue_purpose_input_digest_owner_rejected(self):
        for mutation in ('author','issue','purpose','owner','digest','version'):
            api=PreparationAPI(self.v)
            if mutation=='author': api.comment['user']={'login':'other','id':1,'type':'User'}
            else:
                body=api.comment['body']; request=p.loads(body.split(p.REQUEST_START)[1].split(p.REQUEST_END)[0])
                key={'digest':'input_digest','version':'input_version'}.get(mutation,mutation)
                request[key]='wrong'
                api.comment['body']=body.replace(body.split(p.REQUEST_START)[1].split(p.REQUEST_END)[0],p.canonical(request))
            with self.assertRaises(ValueError): reconcile_preparation(api,88,self.policy,NOW)
            self.assertEqual([],api.writes)
    def test_duplicate_record_conflict(self):
        self.api.extra=[{**self.api.comment,'id':101}]
        with self.assertRaises(PreparationConflict): self.update()
        self.assertEqual([],self.api.writes)
    def test_old_input_version_cannot_roll_back(self):
        self.update(); old=self.api.comment['body']
        value={**self.v,'input_version':2}
        new=p.generate(value,self.api.config,p.rebase(snapshot(old)['state'],value))['github_record.md']
        start=old.index(p.REQUEST_START); end=old.index(p.REQUEST_END)+len(p.REQUEST_END)
        self.api.comment['body']=old[:start]+new.rstrip()+old[end:]
        self.update(); version2=self.api.comment['body']
        self.api.comment['body']=version2.replace(new.rstrip(),old[start:end])
        with self.assertRaises(ValueError): self.update()
    def test_concurrent_human_edit_no_overwrite(self):
        calls=0
        def hook(path):
            nonlocal calls
            if path=='/issues/comments/100':
                self.api.comment['body']+='\nConcurrent note'; calls+=1
        self.api.hook=hook
        with self.assertRaises(PreparationConflict): self.update()
        self.assertEqual([],self.api.writes); self.assertIn('Concurrent note',self.api.comment['body'])
    def test_unknown_send_no_automatic_resend_and_restart_reconcile(self):
        self.api.fail=OSError('synthetic network failure after write')
        with self.assertRaises(PreparationWriteUnknown): self.update()
        self.assertEqual(1,len(self.api.writes))
        self.api.fail=None
        self.assertEqual('NO_OP',self.update()); self.assertEqual(1,len(self.api.writes))
    def test_read_failure_does_not_publish_success(self):
        def hook(path):
            if path=='/git/ref/heads/main': raise OSError('synthetic unavailable')
        self.api.hook=hook
        with self.assertRaises(OSError): self.update()
        self.assertEqual([],self.api.writes)
    def test_policy_merge_and_exact_main_readback_separate(self):
        self.api.config['issues']={}
        self.api.pull={'number':89,'body':'Refs #88\n','base':{'ref':'main','repo':{'full_name':p.REPOSITORY}},'head':{'sha':HEAD},'merged':True}
        self.update(); state=snapshot(self.api.comment['body'])['state']
        self.assertEqual('WAITING',state['stages']['policy']['status'])
        self.api.config['issues']['88']=self.policy
        self.update(); state=snapshot(self.api.comment['body'])['state']
        self.assertEqual('CONFIRMED',state['stages']['policy']['status'])
    def test_no_record_no_new_comment_and_other_issue_noop(self):
        self.api.comment['body']='Human prose'
        self.assertEqual('NO_RECORD',self.update()); self.assertEqual([],self.api.writes)
        self.assertEqual([],self.api.writes)
    def test_post_write_fact_race_not_success_or_retried(self):
        def hook(path):
            if self.api.writes and path == '/git/ref/heads/main': self.api.main_sha = 'd'*40
        self.api.hook=hook
        with self.assertRaises(PreparationWriteUnknown): self.update()
        self.assertEqual(1,len(self.api.writes))
    def test_broken_shared_snapshot_fail_closed(self):
        self.update(); old=self.api.comment['body']; value=snapshot(old)
        value['state']['input_digest']='broken'
        content=old.split(p.SNAPSHOT_START)[1].split(p.SNAPSHOT_END)[0]
        self.api.comment['body']=old.replace(content,p.canonical(value))
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(1,len(self.api.writes))
    def test_null_issue_transition_history_initial_and_existing_snapshot(self):
        old={**self.v,'issue':None,'input_version':1,'purpose':'synthetic-transition'}
        state=p.mark_unknown(p.new_state(old),'issue')
        current={**old,'issue':88,'input_version':2}
        revised=p.rebase(state,current)
        api=PreparationAPI(current); policy=p.policy_entry(current)
        api.comment['body']=p.generate(current,api.config,revised)['github_record.md']
        self.assertEqual('UPDATED',reconcile_preparation(api,88,policy,NOW))
        saved=snapshot(api.comment['body'])['state']
        self.assertIn(next(iter(state['operations'])),saved['operations'])
        newer={**current,'input_version':3,'start_main_sha':'c'*40}
        next_state=p.rebase(saved,newer)
        api.value=newer; api.issue['number']=88; api.issue['body']='purpose: '+newer['purpose']
        api.config={'schema_version':1,'repository':p.REPOSITORY,'issues':{'88':p.policy_entry(newer)}}
        old_body=api.comment['body']; generated=p.generate(newer,api.config,next_state)['github_record.md']
        start=old_body.index(p.REQUEST_START); end=old_body.index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=old_body[:start]+generated.rstrip()+old_body[end:]
        self.assertEqual('UPDATED',reconcile_preparation(api,88,p.policy_entry(newer),NOW))
        self.assertEqual(2,len(snapshot(api.comment['body'])['state']['input_history']))
    def test_transition_history_rejects_unrelated_old_issue(self):
        current={**self.v,'input_version':2}
        state=p.new_state(current)
        state['input_history']=[{**self.v,'issue':999}]
        with self.assertRaisesRegex(ValueError,'Unrelated or unordered'):
            p.validate_state(state)
    def test_existing_snapshot_rejects_rewritten_owner_history(self):
        self.update(); old=self.api.comment['body']; saved=snapshot(old)['state']
        current={**self.v,'input_version':2}
        generated=p.generate(current,self.api.config,p.rebase(saved,current))['github_record.md']
        request=p.loads(generated.split(p.REQUEST_START)[1].split(p.REQUEST_END)[0])
        request['input_history'][0]['start_main_sha']='c'*40
        replacement=p.REQUEST_START+p.canonical(request)+p.REQUEST_END
        start=old.index(p.REQUEST_START); end=old.index(p.REQUEST_END)+len(p.REQUEST_END)
        self.api.comment['body']=old[:start]+replacement+old[end:]
        with self.assertRaisesRegex(ValueError,'differs from saved history'): self.update()
        self.assertEqual(1,len(self.api.writes))
    def test_main_preparation_failure_cannot_safe_stop_gate(self):
        from tools import update_automation_dashboard as writer
        self.api.comment['user']={'login':'wrong','id':1,'type':'User'}
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'config.json'; config.write_text(json.dumps(self.api.config))
            with patch('sys.argv',['writer','--config',str(config)]), \
                 patch.dict('os.environ',{'GITHUB_REPOSITORY':p.REPOSITORY,'GH_TOKEN':'synthetic'}), \
                 patch.object(writer,'GitHub',return_value=self.api), \
                 patch.object(writer,'reconcile',return_value='NO_OP') as gate, \
                 patch.object(writer,'safe_stop') as stop, \
                 patch('builtins.print'):
                self.assertEqual(1,writer.main()); gate.assert_called_once(); stop.assert_not_called()
        self.assertEqual([],self.api.writes)
    def test_gate_failures_survive_review_and_sync_success(self):
        policy,facts,report=fixtures()
        policy=self.policy
        facts['pr']=None; facts['pr_comments']=[]
        for failed in ('FAILED','CANCELLED'):
            implementation={'target_sha':HEAD,'action_type':'implementation_task','purpose_id':p.PURPOSE,
                'state':failed,'run_id':'synthetic-implementation','attempt':1,'retry_of':None}
            implementation['dedup_key']=dedup_key(88,implementation)
            for action in ('work_review','local_main_sync'):
                other={**implementation,'action_type':action,'state':'SUCCEEDED','run_id':'synthetic-'+action}
                other['dedup_key']=dedup_key(88,other)
                comments=[record(RECEIPT,{'schema_version':1,'repository':p.REPOSITORY,'issue':88,'active':True,'dispatch':item},ident=n)
                          for n,item in enumerate((implementation,other),100)]
                facts['issue_comments']=comments
                state=evaluate(88,policy,None,facts)
                self.assertNotEqual('PASS',state['merge_gate']['status'])
                self.assertIn('Initial implementation is not running or successful',state['blockers'])
                self.assertEqual(state,parse_state(render(state),88,policy))


if __name__=='__main__': unittest.main()
