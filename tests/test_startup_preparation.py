"""Issue #88 synthetic acceptance tests. No real Work, dispatch or measurement."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import startup_preparation as p
from tools.preparation_github import (reconcile_preparation, PreparationConflict,
                                     PreparationWriteUnknown, snapshot, read_facts)
from tools.automation_dashboard import evaluate, initial_state, render, parse_state, RECEIPT, dedup_key
from tests.test_automation_dashboard import ROOT, NOW, HEAD, record, fixtures


def input_fixture():
    return json.loads((ROOT / 'docs/startup-preparation-input.json').read_text(encoding='utf-8'))


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
        self.comment = {'id':100,'body':'Human before\n'+body+'\nHuman after','user':value['owner'],
                        'issue_url':f'https://api.github.com/repos/{p.REPOSITORY}/issues/{value["issue"]}',
                        'updated_at':NOW}
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
        config=json.loads((ROOT/'.github/automation-dashboard.json').read_text(encoding='utf-8'))
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
            self.assertEqual(self.state,p.validate_state(p.loads(path.read_text(encoding='utf-8'))))
            path.write_text('{broken')
            with self.assertRaises(ValueError): p.atomic_save(path,self.state)
            self.assertEqual('{broken',path.read_text(encoding='utf-8'))
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
            input_path.write_text(p.canonical(self.v),encoding='utf-8'); p.atomic_save(state_path,p.resume(self.state,self.facts,NOW))
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(state_path),
                                  '--output',str(base/'generated'),'--github-read']), \
                 patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.preparation_github.read_facts',side_effect=OSError('synthetic offline')), \
                 patch('builtins.print'):
                with self.assertRaises(OSError): p.main()
            saved=p.validate_state(p.loads(state_path.read_text(encoding='utf-8')))
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
            input_path.write_text(p.canonical(self.v),encoding='utf-8'); p.atomic_save(state_path,state)
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(state_path),
                                   '--output',str(base/'generated'),'--github-read']), \
                 patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.update_automation_dashboard.GitHub',return_value=api), patch('builtins.print'):
                self.assertEqual(0,p.main())
            saved=p.validate_state(p.loads(state_path.read_text(encoding='utf-8')))
            self.assertEqual('CONFIRMED',saved['operations'][key]['status'])
            self.assertEqual(89,saved['operations'][key]['external_id']); self.assertEqual([],api.writes)


class GenericTargets(unittest.TestCase):
    def test_owner_facts_direct_cli_persist_summary_and_noop(self):
        value=input_fixture()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); input_path=base/'input.json'; facts_path=base/'owner.json'
            input_path.write_text(p.canonical(value),encoding='utf-8'); facts_path.write_text(p.canonical(owner_facts(value)),encoding='utf-8')
            command=[sys.executable,'-B',str(ROOT/'tools/startup_preparation.py'),
                     '--input',str(input_path),'--config',str(ROOT/'.github/automation-dashboard.json'),
                     '--state',str(base/'state.json'),'--output',str(base/'out'),
                     '--owner-facts',str(facts_path)]
            environment={**os.environ,'PYTHONIOENCODING':'cp1252'}
            first=subprocess.run(command,cwd=base,capture_output=True,text=True,encoding='utf-8',env=environment)
            self.assertEqual(0,first.returncode,first.stderr)
            state=p.loads((base/'state.json').read_text(encoding='utf-8'))
            self.assertEqual('CONFIRMED',state['stages']['review']['status'])
            self.assertEqual('CONFIRMED',state['stages']['publication']['status'])
            self.assertEqual('WAITING',state['status']); self.assertFalse(state['shared_persistence'])
            self.assertIn('review: CONFIRMED',first.stdout)
            self.assertIn('正式Dashboard未適用',first.stdout)
            before=(base/'state.json').read_bytes()
            second=subprocess.run(command,cwd=base,capture_output=True,text=True,encoding='utf-8',env=environment)
            self.assertEqual(0,second.returncode,second.stderr)
            self.assertEqual(before,(base/'state.json').read_bytes())

    def test_owner_facts_with_github_read_complete_and_pending_real_event(self):
        value=input_fixture(); api=PreparationAPI(value); observed=owner_facts(value)
        dash=initial_state(value['issue'],p.policy_entry(value))
        api.extra=[{'id':123,'user':{'login':'github-actions[bot]','id':41898282,'type':'Bot'},
                    'body':render(dash)}]
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); input_path=base/'input.json'; facts_path=base/'owner.json'
            input_path.write_text(p.canonical(value),encoding='utf-8'); facts_path.write_text(p.canonical(observed),encoding='utf-8')
            command=['cli','--input',str(input_path),'--config',str(ROOT/'.github/automation-dashboard.json'),
                     '--state',str(base/'state.json'),'--output',str(base/'out'),
                     '--github-read','--owner-facts',str(facts_path)]
            with patch('sys.argv',command), patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.update_automation_dashboard.GitHub',return_value=api),patch('builtins.print'):
                self.assertEqual(0,p.main())
            saved=p.loads((base/'state.json').read_text(encoding='utf-8'))
            self.assertEqual('PREPARATION_COMPLETE',saved['status']); self.assertEqual([],api.writes)
            observed['review'].update(event_verified=False,actual_event=None)
            facts_path.write_text(p.canonical(observed),encoding='utf-8')
            with patch('sys.argv',command), patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                 patch('tools.update_automation_dashboard.GitHub',return_value=api),patch('builtins.print'):
                self.assertEqual(0,p.main())
            saved=p.loads((base/'state.json').read_text(encoding='utf-8'))
            self.assertEqual('WAITING',saved['stages']['review']['status'])
            self.assertEqual(value['actors']['dispatch'],saved['next_owner'])

    def test_missing_dashboard_does_not_hide_policy_merge_or_readback_wait(self):
        value=input_fixture(); facts=facts_fixture(value)
        facts.pop('dashboard'); facts.pop('main_policy')
        facts['policy_pr']={'number':89,'merged':False}
        saved=p.resume(p.new_state(value),facts,NOW)
        self.assertEqual('human merge owner',saved['next_owner'])
        facts['policy_pr']['merged']=True
        saved=p.resume(saved,facts,NOW)
        self.assertEqual(value['actors']['dispatch'],saved['next_owner'])
        self.assertIn('read back',saved['next_action'])

    def test_old_owner_event_cannot_roll_back_local_or_shared_evidence(self):
        from tools.preparation_github import apply_owner_facts
        value=input_fixture(); observed=owner_facts(value)
        state=p.resume(p.new_state(value),apply_owner_facts(facts_fixture(value),observed,value),NOW)
        old=copy.deepcopy(observed); old['observed_at']='2026-01-01T00:00:00Z'
        old['review'].update(event_verified=False,actual_event=None)
        with self.assertRaisesRegex(ValueError,'Older owner observation'):
            p.resume(state,apply_owner_facts(facts_fixture(value),old,value),NOW)
        api=PreparationAPI(value); policy=p.policy_entry(value)
        api.comment['body']=p.generate(value,api.config,owner_facts=observed)['github_record.md']
        reconcile_preparation(api,88,policy,NOW)
        saved=api.comment['body']; start=saved.index(p.REQUEST_START); end=saved.index(p.REQUEST_END)+len(p.REQUEST_END)
        replacement=p.generate(value,api.config,owner_facts=old)['github_record.md'].rstrip()
        api.comment['body']=saved[:start]+replacement+saved[end:]
        with self.assertRaisesRegex(ValueError,'Older owner observation'):
            reconcile_preparation(api,88,policy,NOW)
        self.assertEqual(1,len(api.writes))

    def test_missing_owner_facts_do_not_erase_local_watermark(self):
        from tools.preparation_github import apply_owner_facts
        value=input_fixture(); recent=owner_facts(value)
        recent['review'].update(event_verified=False,actual_event=None)
        state=p.resume(p.new_state(value),apply_owner_facts(facts_fixture(value),recent,value),NOW)
        missing=facts_fixture(value); missing.pop('review'); missing.pop('publication')
        state=p.resume(state,missing,NOW)
        self.assertEqual('UNCONFIRMED',state['stages']['review']['status'])
        p.validate_state(state)
        old=owner_facts(value); old['observed_at']='2026-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Older owner observation'):
            p.resume(state,apply_owner_facts(facts_fixture(value),old,value),NOW)
        self.assertNotEqual('PREPARATION_COMPLETE',state['status'])
        changed={**value,'input_version':value['input_version']+1,'start_main_sha':'c'*40}
        moved=p.rebase(state,changed); p.validate_state(moved)
        rebound=owner_facts(changed); rebound['observed_at']=old['observed_at']
        accepted=p.resume(moved,apply_owner_facts(facts_fixture(changed),rebound,changed),NOW)
        self.assertEqual(p.digest(changed),accepted['owner_observations']['review']['input_digest'])
        legacy=p.resume(p.new_state(value),apply_owner_facts(facts_fixture(value),recent,value),NOW)
        legacy.pop('owner_observations')
        migrated=p.resume(legacy,missing,NOW)
        with self.assertRaisesRegex(ValueError,'Older owner observation'):
            p.resume(migrated,apply_owner_facts(facts_fixture(value),old,value),NOW)

    def test_cli_gap_rejects_old_owner_success_with_and_without_github_read(self):
        value=input_fixture(); recent=owner_facts(value)
        recent['review'].update(event_verified=False,actual_event=None)
        old=owner_facts(value); old['observed_at']='2026-01-01T00:00:00Z'
        for github_read in (False,True):
            with self.subTest(github_read=github_read), tempfile.TemporaryDirectory() as directory:
                base=Path(directory); api=PreparationAPI(value)
                (base/'input.json').write_text(p.canonical(value),encoding='utf-8')
                (base/'owner.json').write_text(p.canonical(recent),encoding='utf-8')
                command=['cli','--input',str(base/'input.json'),'--config',str(ROOT/'.github/automation-dashboard.json'),
                         '--state',str(base/'state.json'),'--output',str(base/'out')]
                if github_read: command.append('--github-read')
                owner_args=['--owner-facts',str(base/'owner.json')]
                def run(args):
                    if not github_read:
                        return subprocess.run([sys.executable,'-B',str(ROOT/'tools/startup_preparation.py'),*args[1:]],
                                              cwd=directory,capture_output=True,encoding='utf-8')
                    with patch('sys.argv',args),patch.dict('os.environ',{'GH_TOKEN':'synthetic'}), \
                         patch('tools.update_automation_dashboard.GitHub',return_value=api),patch('builtins.print'):
                        return p.main()
                result=run(command+owner_args)
                self.assertEqual(0,result if github_read else result.returncode)
                result=run(command)
                self.assertEqual(0,result if github_read else result.returncode)
                saved=(base/'state.json').read_text(encoding='utf-8')
                self.assertNotEqual('PREPARATION_COMPLETE',p.loads(saved)['status'])
                self.assertEqual('UNCONFIRMED',p.loads(saved)['stages']['review']['status'])
                (base/'owner.json').write_text(p.canonical(old),encoding='utf-8')
                if github_read:
                    with self.assertRaisesRegex(ValueError,'Older owner observation'): run(command+owner_args)
                else:
                    result=run(command+owner_args)
                    self.assertNotEqual(0,result.returncode); self.assertIn('Older owner observation',result.stderr)
                after=p.loads((base/'state.json').read_text(encoding='utf-8'))
                self.assertEqual(p.loads(saved)['owner_observations'],after['owner_observations'])
                self.assertNotEqual('PREPARATION_COMPLETE',after['status'])
                if not github_read: self.assertEqual(p.loads(saved),after)
                self.assertEqual([],api.writes)

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
                restored=p.validate_state(p.loads(path.read_text(encoding='utf-8')))
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
            input_path.write_text(p.canonical(self.v),encoding='utf-8'); facts_path.write_text(p.canonical(observed),encoding='utf-8')
            with patch('sys.argv',['cli','--input',str(input_path),'--state',str(base/'state.json'),
                                   '--output',str(base/'generated'),'--owner-facts',str(facts_path)]), \
                 patch('builtins.print'):
                self.assertEqual(0,p.main())
            self.api.comment['body']=(base/'generated/github_record.md').read_text(encoding='utf-8')
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

    def test_shared_missing_owner_facts_preserve_watermark_and_reject_old_success(self):
        recent=owner_facts(self.v); recent['review'].update(event_verified=False,actual_event=None)
        def replace_owner(observation):
            body=self.api.comment['body']; start=body.index(p.REQUEST_START); end=body.index(p.REQUEST_END)+len(p.REQUEST_END)
            request=p.generate(self.v,self.api.config,owner_facts=observation)['github_record.md'].rstrip()
            self.api.comment['body']=body[:start]+request+body[end:]
        replace_owner(recent); self.update()
        replace_owner(None); self.update()
        state=snapshot(self.api.comment['body'])['state']
        self.assertEqual(NOW,state['owner_observations']['review']['observed_at'])
        self.assertEqual('UNCONFIRMED',state['stages']['review']['status'])
        old=owner_facts(self.v); old['observed_at']='2026-01-01T00:00:00Z'
        replace_owner(old)
        with self.assertRaisesRegex(ValueError,'Older owner observation'): self.update()
        self.assertEqual(2,len(self.api.writes))

    def test_multiple_unpublished_input_transitions_preserve_snapshot_and_operations(self):
        local=p.mark_unknown(p.new_state(self.v),'implementation_task')
        self.api.comment['body']=p.generate(self.v,self.api.config,local)['github_record.md']
        self.update(); saved=snapshot(self.api.comment['body'])['state']
        intermediate={**self.v,'input_version':2,'start_main_sha':'c'*40}
        current={**self.v,'input_version':3,'start_main_sha':'d'*40}
        local=p.rebase(p.rebase(saved,intermediate),current); p.validate_state(local)
        self.api.value=current; self.api.config['issues']['88']=p.policy_entry(current)
        body=self.api.comment['body']; start=body.index(p.REQUEST_START); end=body.index(p.REQUEST_END)+len(p.REQUEST_END)
        request=p.generate(current,self.api.config,local)['github_record.md'].rstrip()
        self.api.comment['body']=body[:start]+request+body[end:]
        self.assertEqual('UPDATED',reconcile_preparation(self.api,88,p.policy_entry(current),NOW))
        state=snapshot(self.api.comment['body'])['state']
        self.assertEqual([self.v,intermediate],state['input_history'])
        self.assertEqual(saved['operations'],state['operations'])
        self.assertEqual('UNKNOWN',next(iter(state['operations'].values()))['status'])
        self.assertEqual('NO_OP',reconcile_preparation(self.api,88,p.policy_entry(current),NOW))
        self.assertEqual(2,len(self.api.writes))
        request_data=p.loads(request.split(p.REQUEST_START)[1].split(p.REQUEST_END)[0])
        request_data['operations']={}
        body=self.api.comment['body']; start=body.index(p.REQUEST_START); end=body.index(p.REQUEST_END)+len(p.REQUEST_END)
        self.api.comment['body']=body[:start]+p.REQUEST_START+p.canonical(request_data)+p.REQUEST_END+body[end:]
        with self.assertRaisesRegex(ValueError,'removed unresolved operation'):
            reconcile_preparation(self.api,88,p.policy_entry(current),NOW)
        self.assertEqual(2,len(self.api.writes))
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
