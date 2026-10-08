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
    def __init__(self):self.refs={};self.commits={};self.posts=[];self.fail=None;self.competitor=None
    def get(self,path):
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
        self.assertEqual(len(api.posts),1) # inert commit only, no ref send
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

if __name__=='__main__':unittest.main()
