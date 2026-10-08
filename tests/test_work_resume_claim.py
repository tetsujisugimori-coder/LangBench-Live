"""Capability/ref fixtures validate code, never real Work delivery or execution."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from tools import startup_preparation as p
from tools import work_owner_resume as w, work_resume_claim as c
from tests.test_work_owner_resume import fixture, T1, T2, T3, URL, MERGE

SECRET='12'*32
PUBLIC=hashlib.sha256(bytes.fromhex(SECRET)).hexdigest()


def capability_fixture():
    value,facts=fixture()
    value['schema_version']=2
    value['authorization']=dict(kind='live_smoke',authorization_ref='Issue96',effect='read_only')
    facts['resume_authorization']=copy.deepcopy(value['authorization'])
    value['work']['run_id']=None
    value['work']['identity']=dict(scheme='capability_v1',public_id=PUBLIC,source='local_csprng',
        assurance=c.ASSURANCE,route='automatic',conversation_id=None,cloud_task_id=None,authorization_comment_id=None)
    for field in ('claim','receipt','next_action'):
        value[field].pop('run_id');value[field]['execution_id']=PUBLIC
    value['claim'].update(ref=c.reservation_ref(value),commit_sha='f'*40)
    value['next_action']['effect']='read_only'
    facts['policy']['resume_protocol']=2
    facts['resume_reservation']=dict(ref=c.reservation_ref(value),commit_sha='f'*40,record=c.binding(value))
    return value,facts


class RefAPI:
    root='https://api.github.com/repos/tetsujisugimori-coder/LangBench-Live'
    def __init__(self):self.refs={};self.commits={};self.posts=[];self.gets=[];self.fail=None;self.competitor=None
    def get(self,path):
        self.gets.append(path)
        if path.startswith('/git/matching-refs/'):
            return [copy.deepcopy(x) for x in self.refs.values() if x['ref'].startswith('refs/'+path.removeprefix('/git/matching-refs/'))]
        if path.startswith('/git/ref/'):return copy.deepcopy(self.refs['refs/'+path.removeprefix('/git/ref/')])
        if path=='/git/commits/'+MERGE:return dict(sha=MERGE,tree={'sha':'b'*40})
        if path.startswith('/git/commits/'):return copy.deepcopy(self.commits[path.removeprefix('/git/commits/')])
        raise AssertionError(path)
    def request(self,path,method,data):
        self.posts.append((path,copy.deepcopy(data)))
        if path.endswith('/git/commits'):
            ident=hashlib.sha1(p.canonical(data).encode()).hexdigest()
            self.commits[ident]=dict(sha=ident,message=data['message'],parents=[{'sha':x} for x in data['parents']])
            return dict(sha=ident)
        if self.competitor:self.competitor(self,data)
        if data['ref'] in self.refs:raise ValueError('ref exists')
        if self.fail=='before':raise OSError('unknown response')
        self.refs[data['ref']]=dict(ref=data['ref'],object={'type':'commit','sha':data['sha']})
        if self.fail=='after':raise OSError('accepted, response lost')
        return copy.deepcopy(self.refs[data['ref']])


class CapabilityTests(unittest.TestCase):
    def test_actual_read_only_smoke_creates_receipt_and_operation_without_writes(self):
        from tools.automation_dashboard import BOT,initial_state,render,sync_evidence,dedup_key
        value,facts=capability_fixture();value['receipt']=None;value['next_action']=None
        dashboard=initial_state(value['issue'],facts['policy'])
        dashboard.update(pr=value['pr'],head_sha=value['reviewed_head_sha'],merge_sha=value['merge_sha'],
            current_state='LOCAL_SYNCED',local_sync=sync_evidence(facts,value['merge_sha']))
        dispatch=dict(target_sha=MERGE,action_type='implementation_task',purpose_id=w.PURPOSE,
                      state='SUCCEEDED',run_id='synthetic-cloud-task',attempt=1,retry_of=None)
        dispatch['dedup_key']=dedup_key(value['issue'],dispatch)
        dashboard.update(dispatches=[dispatch],active_action=dispatch['action_type'],purpose_id=w.PURPOSE,
                         dedup_key=dispatch['dedup_key'],dispatch_state='SUCCEEDED',active_run_id=dispatch['run_id'])
        facts['dashboard_comment_id']=126
        facts['issue_comments'].append(dict(id=126,user=BOT,body=render(dashboard)))
        updated=w.read_only_smoke(value,facts)
        self.assertEqual(updated['receipt']['waiting_comment_id'],123)
        self.assertEqual(updated['next_action']['effect'],'read_only')
        self.assertEqual(w.observe(updated,facts)['status'],'OBSERVED')
        facts['issue_comments'][-1]['user']=value['owner']
        with self.assertRaises(ValueError):w.read_only_smoke(value,facts)

    def test_production_transport_rejects_other_mutations(self):
        from unittest.mock import patch
        from tools.update_automation_dashboard import GitHub
        value,_=capability_fixture();api=c.ReservationGitHub('synthetic',value)
        with patch.object(api,'_send_request',side_effect=AssertionError('must not send')):
            for path,method in [('/git/refs','PATCH'),('/issues/96/comments','POST'),('/git/refs','DELETE')]:
                with self.assertRaises(ValueError):api.request(api.root+path,method,{})
        with self.assertRaises(ValueError):GitHub('synthetic').request('/repos/'+value['repository']+'/git/refs','POST',{})

    def test_binding_and_second_read_persist_without_run_substitution(self):
        value,facts=capability_fixture()
        out=w.observe(value,facts)
        self.assertEqual(out['status'],'OBSERVED',out['reason'])
        self.assertIsNone(out['claimed_run_id'])
        self.assertEqual(out['claimed_execution_id'],PUBLIC)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'observation.json';w.save_observation(path,out)
            loaded=p.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(w.observe(value,facts,loaded),out)
    def test_identifier_kind_and_possession_rejected(self):
        for name in ('conversation_id','cloud_task_id'):
            value,facts=capability_fixture();value['work']['identity'][name]=PUBLIC
            with self.assertRaises(ValueError):w.validate(value)
        value,_=capability_fixture();value['work']['run_id']='some-delivery'
        with self.assertRaises(ValueError):w.validate(value)
        value,_=capability_fixture()
        with self.assertRaises(ValueError):c.verify_possession(value,'34'*32)
        c.verify_possession(value,SECRET)
    def test_redelivery_and_other_work_share_permanent_slot(self):
        value,_=capability_fixture();api=RefAPI();journal={};persist=lambda x:None
        saved=c.acquire(api,value,SECRET,journal,persist)
        self.assertEqual(len(api.posts),2)
        self.assertEqual(c.acquire(api,value,SECRET,journal,persist),saved)
        self.assertEqual(len(api.posts),2)
        second=copy.deepcopy(value);second['event']['delivery_id']='redelivery'
        self.assertEqual(c.reservation_ref(second),c.reservation_ref(value))
        with self.assertRaises(ValueError):c.acquire(api,second,SECRET,{},persist)
        second=copy.deepcopy(value);secret='34'*32
        second['work']['identity']['public_id']=hashlib.sha256(bytes.fromhex(secret)).hexdigest()
        for field in ('claim','receipt','next_action'):second[field]['execution_id']=second['work']['identity']['public_id']
        with self.assertRaises(ValueError):c.acquire(api,second,secret,{},persist)
        self.assertEqual(len(api.posts),2)
    def test_concurrent_create_ref_loser_stops(self):
        value,_=capability_fixture();api=RefAPI()
        def competitor(api,data):
            record=c.binding(value);record['work']['identity']['public_id']='e'*64
            api.commits['a'*40]=dict(sha='a'*40,message=p.canonical(record),parents=[{'sha':MERGE}])
            api.refs[data['ref']]=dict(ref=data['ref'],object={'type':'commit','sha':'a'*40})
        api.competitor=competitor;journal={}
        with self.assertRaises(ValueError):c.acquire(api,value,SECRET,journal,lambda x:None)
        self.assertEqual(journal['status'],'ATTEMPTING')
    def test_unknown_write_reconcile_and_crash_never_resend(self):
        for failure in ('before','after'):
            value,_=capability_fixture();api=RefAPI();api.fail=failure;journal={}
            if failure=='before':
                with self.assertRaises(KeyError):c.acquire(api,value,SECRET,journal,lambda x:None)
            else:c.acquire(api,value,SECRET,journal,lambda x:None)
            loaded=p.loads(p.canonical(journal));posts=len(api.posts)
            if failure=='before':
                with self.assertRaises(KeyError):c.acquire(api,value,SECRET,loaded,lambda x:None)
            else:c.acquire(api,value,SECRET,loaded,lambda x:None)
            self.assertEqual(len(api.posts),posts)
    def test_journal_failure_prevents_ref_post(self):
        value,_=capability_fixture();api=RefAPI()
        def fail(x):raise OSError('disk full')
        with self.assertRaises(OSError):c.acquire(api,value,SECRET,{},fail)
        self.assertEqual(len(api.posts),0) # even inert commit is journaled before send
    def test_mutation_and_missing_reservation_never_promote(self):
        value,facts=capability_fixture();value['next_action']['effect']='external_write'
        self.assertEqual(w.observe(value,facts)['status'],'STOPPED')
        value,facts=capability_fixture();facts.pop('resume_reservation')
        self.assertEqual(w.observe(value,facts)['status'],'STOPPED')
        value,facts=capability_fixture();facts['policy'].pop('resume_protocol')
        self.assertEqual(w.observe(value,facts)['status'],'STOPPED')
    def test_manual_read_only_handoff_is_not_automatic_success_or_takeover(self):
        value,facts=capability_fixture();identity=value['work']['identity']
        identity.update(route='manual',authorization_comment_id=125);value['claim']=None
        record=dict(schema_version=1,kind='i01_manual_read_only',binding=c.binding(value),
                    retained_automatic_status='UNVERIFIED',allowed_effect='read_only')
        facts['issue_comments'].append(dict(id=125,user=value['owner'],body='<!-- langbench-i01-manual:v1\n'+p.canonical(record)+'\n-->'))
        out=w.observe(value,facts)
        self.assertEqual(out['status'],'MANUAL_OBSERVED',out['reason'])
        value['next_action']['effect']='external_write'
        self.assertEqual(w.observe(value,facts)['status'],'STOPPED')
    def test_new_negative_cannot_be_rolled_back_by_old_pass(self):
        value,facts=capability_fixture();prior=w.observe(value,facts)
        positive=copy.deepcopy(value);value['next_action'].update(status='UNKNOWN',observed_at='2026-10-08T00:04:00Z')
        negative=w.observe(value,facts,prior)
        for _ in range(2):
            negative=w.observe(positive,facts,p.loads(p.canonical(negative)))
            self.assertEqual(negative['status'],'STOPPED')
            self.assertEqual(negative['evidence_history']['action']['status'],'UNKNOWN')

class ReservationCLITests(unittest.TestCase):
    def run_cli(self, root, api, facts, *, read_error=None, save=None):
        from unittest.mock import patch
        import contextlib
        import io
        argv=['claim','--handoff',str(root/'handoff.json'),'--capability-file',str(root/'secret'),
              '--state',str(root/'state.json')]
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('sys.argv',argv))
            stack.enter_context(patch.object(c,'ReservationGitHub',return_value=api))
            stack.enter_context(patch.object(w,'ObservationGitHub'))
            reads=stack.enter_context(patch.object(w,'read_facts',side_effect=read_error,return_value=facts))
            if save is not None:stack.enter_context(patch.object(w,'save_observation',side_effect=save))
            output=stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result=c.main()
        return result,p.loads(output.getvalue()),reads.call_count

    def setup_files(self, root):
        value,facts=capability_fixture()
        (root/'handoff.json').write_text(p.canonical(value),encoding='utf-8')
        (root/'secret').write_text(SECRET,encoding='utf-8')
        return value,facts

    def test_preflight_and_target_failure_recover_without_losing_diagnostics(self):
        for kind in ('preflight','scope'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);value,facts=self.setup_files(root);api=RefAPI()
                bad=copy.deepcopy(facts)
                if kind=='preflight':bad['main_sha']='d'*40
                else:bad['resume_authorization']={}
                code,out,_=self.run_cli(root,api,bad)
                self.assertEqual(code,1);self.assertEqual(api.posts,[])
                stopped=p.loads((root/'state.json').read_text(encoding='utf-8'))
                self.assertEqual(stopped['journal'],{});self.assertEqual(len(stopped['diagnostics']),1)
                code,out,reads=self.run_cli(root,api,facts)
                self.assertEqual((code,reads),(0,2));self.assertEqual(len(api.posts),2)
                final=c.load_state(root/'state.json',value)
                self.assertEqual(final['diagnostics'],stopped['diagnostics'])
                self.assertEqual(final['journal']['status'],'ACQUIRED')
                self.assertEqual(self.run_cli(root,api,facts)[0],0);self.assertEqual(len(api.posts),2)

    def test_durable_unknown_ref_and_crash_are_get_only_after_restart(self):
        for mode in ('before','after','crash'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);value,facts=self.setup_files(root);api=RefAPI()
                api.fail=mode if mode!='crash' else None
                if mode=='crash':
                    original=api.request
                    def crash(path,method,data):
                        response=original(path,method,data)
                        if path.endswith('/git/refs'):raise KeyboardInterrupt('process stopped')
                        return response
                    api.request=crash
                    with self.assertRaises(KeyboardInterrupt):self.run_cli(root,api,facts)
                    api.request=original
                else:self.assertEqual(self.run_cli(root,api,facts)[0],1 if mode=='before' else 0)
                old=c.load_state(root/'state.json',value);self.assertTrue(old['journal']['commit_sha'])
                posts=len(api.posts);api.fail=None;api.gets=[]
                code,out,_=self.run_cli(root,api,facts)
                self.assertIn('/git/ref/'+c.reservation_ref(value).removeprefix('refs/'),api.gets)
                self.assertEqual(code,1 if mode=='before' else 0);self.assertEqual(len(api.posts),posts)
                final=c.load_state(root/'state.json',value)
                for key in ('binding','commit_sha','ref'):self.assertEqual(final['journal'][key],old['journal'][key])
                self.assertEqual(final['diagnostics'][:len(old['diagnostics'])],old['diagnostics'])

    def test_save_failure_never_sends_ref_and_preserves_last_durable_phase(self):
        for phase,expected_posts in (('commit',0),('ref',1)):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);value,facts=self.setup_files(root);api=RefAPI();original=w.save_observation
                def save(path,record):
                    if record.get('journal',{}).get('phase')==phase:raise OSError('disk full')
                    original(path,record)
                self.assertEqual(self.run_cli(root,api,facts,save=save)[0],1)
                self.assertEqual(len(api.posts),expected_posts)
                self.assertFalse(api.refs)
                if phase=='ref':
                    persisted=c.load_state(root/'state.json',value)
                    self.assertEqual(persisted['journal']['phase'],'commit')
                    self.assertEqual(self.run_cli(root,api,facts)[0],1)
                    self.assertEqual(len(api.posts),1)

    def test_commit_response_unknown_is_durable_and_never_resent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);value,facts=self.setup_files(root);api=RefAPI();original=api.request
            def lost(path,method,data):
                original(path,method,data);raise OSError('commit response lost')
            api.request=lost
            self.assertEqual(self.run_cli(root,api,facts)[0],1)
            self.assertEqual(c.load_state(root/'state.json',value)['journal']['phase'],'commit')
            api.request=original
            self.assertEqual(self.run_cli(root,api,facts)[0],1);self.assertEqual(len(api.posts),1)

    def test_corrupt_incomplete_binding_and_secret_mismatch_preserve_records(self):
        for kind in ('json','incomplete','legacy_stop','binding','secret','contradictory'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);value,facts=self.setup_files(root);api=RefAPI()
                self.assertEqual(self.run_cli(root,api,facts)[0],0)
                state=root/'state.json';record=c.load_state(state,value)
                if kind=='json':state.write_text('{broken',encoding='utf-8')
                elif kind=='legacy_stop':state.write_text(p.canonical(dict(status='STOPPED',reason='OSError')),encoding='utf-8')
                elif kind=='secret':(root/'secret').write_text('34'*32,encoding='utf-8')
                else:
                    if kind=='incomplete':record['journal'].pop('binding')
                    if kind=='binding':record['journal']['binding']['event']['delivery_id']='other'
                    if kind=='contradictory':record['journal']['phase']='commit'
                    state.write_text(p.canonical(record),encoding='utf-8')
                before=state.read_bytes();posts=len(api.posts)
                for _ in range(2):self.assertEqual(self.run_cli(root,api,facts)[0],1)
                self.assertEqual(len(api.posts),posts)
                if kind!='secret':
                    self.assertEqual(state.read_bytes(),before)
                    diagnostics=p.loads((root/'state.json.diagnostics.json').read_text(encoding='utf-8'))
                    self.assertEqual(len(diagnostics),2)
                else:
                    after=c.load_state(state,value)
                    self.assertEqual(after['journal'],record['journal']);self.assertEqual(len(after['diagnostics']),2)

    def test_competitor_and_legacy_attempt_statuses_remain_get_only(self):
        for status in ('ATTEMPTING','UNKNOWN','ACQUIRED'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);value,facts=self.setup_files(root);api=RefAPI();journal={}
                saved=c.acquire(api,value,SECRET,journal,lambda record:None)
                journal.pop('phase');journal['status']=status;journal['diagnostic']={'reason':'retained'}
                state=root/'state.json';state.write_text(p.canonical(journal),encoding='utf-8')
                self.assertEqual(self.run_cli(root,api,facts)[0],0)
                migrated=c.load_state(state,value)
                self.assertEqual(migrated['diagnostics'],[{'reason':'retained'}])
                competitor=copy.deepcopy(saved['record']);competitor['work']['identity']['public_id']='e'*64
                api.commits[saved['commit_sha']]['message']=p.canonical(competitor)
                for _ in range(2):self.assertEqual(self.run_cli(root,api,facts)[0],1)
                self.assertEqual(len(api.posts),2)
                final=c.load_state(state,value)
                self.assertEqual(final['journal']['binding'],journal['binding'])
                self.assertEqual(final['journal']['commit_sha'],journal['commit_sha'])

    def test_prewrite_network_failure_recovers_with_same_state_and_arguments(self):
        from unittest.mock import patch
        import contextlib
        import io
        value,facts=capability_fixture();api=RefAPI()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);handoff=root/'handoff.json';secret=root/'secret';state=root/'state.json'
            handoff.write_text(p.canonical(value),encoding='utf-8');secret.write_text(SECRET,encoding='utf-8')
            argv=['claim','--handoff',str(handoff),'--capability-file',str(secret),'--state',str(state)]
            with patch('sys.argv',argv),patch.object(c,'ReservationGitHub',return_value=api),patch.object(w,'ObservationGitHub'),contextlib.redirect_stdout(io.StringIO()):
                with patch.object(w,'read_facts',side_effect=OSError('temporary network failure')):
                    self.assertEqual(c.main(),1)
                self.assertTrue(state.exists());self.assertEqual(len(api.posts),0)
                stopped=p.loads(state.read_text(encoding='utf-8'))
                self.assertEqual(stopped['diagnostics'][0]['send_state'],'NOT_SENT')
                with patch.object(w,'read_facts',return_value=facts) as reads:
                    self.assertEqual(c.main(),0)
                    self.assertEqual(reads.call_count,2)
                self.assertEqual(len(api.posts),2)


if __name__=='__main__':unittest.main()
