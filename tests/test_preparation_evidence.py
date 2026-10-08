"""Issue #100 synthetic contract, real CLI subprocess and sole-writer regressions."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import preparation_evidence as e, startup_preparation as p
from tools import preparation_github as g
from tools.automation_dashboard import evaluate, initial_state
from tests.test_startup_preparation import input_fixture, PreparationAPI, owner_facts
from tests.test_automation_dashboard import fixtures, HEAD, NOW

ROOT = Path(__file__).resolve().parents[1]
T0 = '2026-10-08T03:00:00Z'
T1 = '2026-10-08T03:01:00Z'
T2 = '2026-10-08T03:02:00Z'


def fixture(phase='PRE_IMPLEMENTATION'):
    v = input_fixture()
    v.update(schema_version=2, issue=100, purpose='work-owner-resume-i01', phase=phase,
             pr=None if phase == 'PRE_IMPLEMENTATION' else 89,
             head_sha=None if phase == 'PRE_IMPLEMENTATION' else HEAD,
             owner_resume_id=None if phase == 'PRE_IMPLEMENTATION' else 'b'*32,
             registration_prompts={'review': None, 'owner_resume': None})
    for role in e.ROLES:
        # Fixtures are explicitly synthetic; real saved full Prompts belong to Work.
        if role == 'owner_resume' and phase == 'PRE_IMPLEMENTATION': continue
        prompt = e.prompt(v, role) + 'Same full HEAD Ubuntu/Windows CI, independent review, no merge, result handoff.\n日本語の合成詳細指示\n'
        v['registration_prompts'][role] = dict(version=1, text=prompt, digest=hashlib.sha256(prompt.encode()).hexdigest(), events=['closed'] if role == 'owner_resume' else ['opened', 'ready', 'closed'])
    def registration(role):
        ident = v['work_automation_id'] if role == 'review' else v['owner_resume_id']
        return dict(status='SETTINGS_CONFIRMED' if ident else 'NOT_ATTEMPTED', id=ident,
                    settings_version=1 if ident else None, observed_at=T0,
                    settings=dict(enabled=True, prompt=v['registration_prompts'][role]['text'], trigger=dict(
                        repository=v['repository'], pr=v['pr'], events=['closed'] if role == 'owner_resume' else ['opened', 'ready', 'closed'],
                        only_on_merge=role=='owner_resume', title_match='^Issue #100:' if v['pr'] is None else None)) if ident else None,
                    event=None, observation=dict(method='official_ui', evidence_ref='synthetic://saved-screen'))
    record = dict(schema_version=2, repository=v['repository'], issue=100, purpose=v['purpose'], owner=v['owner'],
                  input_version=v['input_version'], input_digest=p.digest(v), start_main_sha=v['start_main_sha'],
                  observed_at=T0, review=registration('review'), owner_resume=registration('owner_resume'),
                  publication=dict(available=True, publisher=v['actors']['publication'], primary_route='synthetic git',
                                   recovery_route='synthetic task output', evidence_ref='synthetic://publication'),
                  waiting_record=None, execution=None, completion_observation=None, stop=None)
    facts = dict(input_digest=p.digest(v), owner_record=record,
                 issue=dict(number=100, repository=v['repository'], purpose=v['purpose'], owner=v['owner']),
                 main_policy=p.policy_entry(v), main_sha=HEAD,
                 dashboard=dict(repository=v['repository'], issue=100, purpose=v['purpose'], comment_id=123), issue_comments=[])
    if v['pr']:
        facts['policy_pr'] = dict(number=89, head_sha=HEAD, merged=False)
    if phase in {'PRE_MERGE', 'POST_MERGE', 'FINISHED'}:
        record['review']['event'] = dict(id='synthetic-delivery', pr=89, head_sha=HEAD, observed_at=T0, evidence_ref='synthetic://review-event')
        body = 'Issue100 synthetic immutable authorized waiting record 日本語'
        record['waiting_record'] = dict(comment_id=777, body_sha256=hashlib.sha256(body.encode()).hexdigest(), head_sha=HEAD,
                                       authorization_ref='synthetic://approval', allowed_action='live_smoke', resume_id=v['owner_resume_id'])
        facts['issue_comments'] = [dict(id=777, body=body, user=v['owner'])]
    return v, record, facts


def writer_api(phase='PRE_IMPLEMENTATION'):
    v, record, facts = fixture(phase)
    api = PreparationAPI(v)
    api.comment['body'] = 'Human before\n' + p.generate(v, api.config, owner_facts=record)['github_record.md'] + '\nHuman after'
    return v, record, facts, api


class EvidenceContractTests(unittest.TestCase):
    def test_stage_future_evidence_not_required(self):
        for phase in ('PRE_IMPLEMENTATION', 'PR_BOUND', 'PRE_MERGE'):
            v,r,f = fixture(phase)
            out = p.resume(p.new_state(v), f, T0)
            self.assertEqual(out['status'], 'PHASE_EVIDENCE_COMPLETE', out['phase_evidence']['missing'])
            self.assertEqual(out['phase_evidence']['i01_live'], 'UNVERIFIED')
            self.assertIsNone(r['execution'])
    def test_postmerge_cannot_copy_preparation_as_execution(self):
        v,r,f=fixture('POST_MERGE')
        out=p.resume(p.new_state(v),f,T0)
        self.assertEqual(out['status'],'WAITING')
        self.assertIn('Actual event',out['phase_evidence']['missing'][-1])
    def test_scope_prompt_and_enabled_negatives(self):
        cases = [('repository','other/repo'),('pr',90),('only_on_merge',False),('title_match','Issue'),('events',['opened'])]
        for key,value in cases:
            v,r,f=fixture('PRE_MERGE'); r['owner_resume']['settings']['trigger'][key]=value
            out=p.resume(p.new_state(v),f,T0)
            self.assertEqual(out['status'],'WAITING',key)
        for role in e.ROLES:
            for field,value in [('enabled',False),('prompt','arbitrary nonempty prompt')]:
                v,r,f=fixture('PRE_MERGE');r[role]['settings'][field]=value
                self.assertEqual(p.resume(p.new_state(v),f,T0)['status'],'WAITING')
    def test_prepr_issue_title_required_saved_detailed_prompt_allowed(self):
        v,r,f=fixture(); self.assertTrue(e.ready(r['review'],v,'review'))
        r['review']['settings']['trigger']['title_match']=None
        self.assertEqual(p.resume(p.new_state(v),f,T0)['status'],'WAITING')
        r['review']['settings']['trigger']['title_match']='^Issue #100:'
        self.assertEqual(p.generate(v,{'schema_version':1,'repository':v['repository'],'issues':{}})['review_registration.md'],r['review']['settings']['prompt'])
    def test_pr_bound_missing_prompt_generation_reports_actual_deficiency(self):
        v,r,f=fixture('PR_BOUND');v['registration_prompts']['owner_resume']=None
        products=p.generate(v,{'schema_version':2,'repository':v['repository'],'issues':{}})
        self.assertNotIn('PR unconfirmed',products['owner_resume_registration.md'])
        self.assertIn('Prompt not yet acquired',products['owner_resume_registration.md'])
        self.assertIn('preserve existing registration',products['owner_resume_registration.md'])
    def test_review_closed_only_and_approved_event_loss_rejected(self):
        v,r,f=fixture();r['review']['settings']['trigger']['events']=['closed']
        self.assertFalse(e.ready(r['review'],v,'review'))
        self.assertEqual(p.resume(p.new_state(v),f,T0)['status'],'WAITING')
        v,r,f=fixture();v['registration_prompts']['review']['events']+=['synchronize','review','comment']
        r['input_digest']=p.digest(v);f['input_digest']=p.digest(v)
        self.assertFalse(e.ready(r['review'],v,'review'))
        r['review']['settings']['trigger']['events']+=['synchronize','review','comment']
        self.assertTrue(e.ready(r['review'],v,'review'))
        v['registration_prompts']['review']['events']=['closed']
        with self.assertRaises(ValueError):p.validate_input(v)
    def test_same_digest_unresolved_cannot_be_erased_before_input_pr_change(self):
        for pending in ('UNKNOWN','ATTEMPTING'):
            v,r,f=fixture('PR_BOUND');s=p.mark_unknown(p.new_state(v),'owner_resume')
            key=e.op_key(v,'owner_resume');s['operations'][key]['status']=pending
            r['owner_resume'].update(status='NOT_ATTEMPTED',id=None,settings=None,settings_version=None)
            s=p.resume(s,f,T0);s=p.loads(p.canonical(s))
            self.assertEqual(s['operations'][key]['status'],pending)
            v2=copy.deepcopy(v);v2.update(input_version=2,pr=90,head_sha='c'*40)
            s=p.rebase(s,v2)
            with self.assertRaises(ValueError):p.mark_unknown(s,'owner_resume')
            self.assertEqual(s['operations'][key]['status'],pending)
            # Same bound actual ID readback is the positive reconciliation boundary.
            v,r,f=fixture('PR_BOUND');s=p.mark_unknown(p.new_state(v),'owner_resume')
            r['owner_resume'].update(status='REGISTERED',settings=None)
            resolved=p.resume(s,f,T0)
            self.assertEqual(resolved['operations'][e.op_key(v,'owner_resume')]['external_id'],v['owner_resume_id'])
    def test_negative_refresh_retains_latest_rejection_time_without_progress(self):
        v,r,f=fixture('PRE_MERGE');r['owner_resume']['settings']['enabled']=False
        r['owner_resume']['observed_at']=T1;r['observed_at']=T1
        s=p.resume(p.new_state(v),f,T1)
        t3='2026-10-08T03:03:00Z';r['owner_resume']['observed_at']=t3;r['observed_at']=t3
        out=p.loads(p.canonical(p.resume(s,f,t3)))
        self.assertEqual(out['last_progress_at'],s['last_progress_at'])
        self.assertEqual(out['owner_watermarks']['owner_resume']['record']['observed_at'],t3)
        r['owner_resume']['observed_at']=T2;r['observed_at']=T2
        r['owner_resume']['settings']['enabled']=True;r['owner_resume']['settings_version']=2
        for _ in range(2):
            out=p.resume(out,f,t3)
            self.assertEqual(out['status'],'WAITING')
            self.assertEqual(out['owner_watermarks']['owner_resume']['record']['observed_at'],t3)
    def test_pr_bound_review_can_preserve_exact_issue_title_filter(self):
        v,r,f=fixture('PR_BOUND');r['review']['settings']['trigger']['title_match']='^Issue #100:'
        self.assertTrue(e.ready(r['review'],v,'review'))
        r['review']['settings']['trigger']['pr']=None
        self.assertFalse(e.ready(r['review'],v,'review'))
    def test_full_prompt_version_digest_strict(self):
        for field,val in [('version',True),('digest','a'*64),('extra',True)]:
            v,r,f=fixture();v['registration_prompts']['review'][field]=val
            with self.assertRaises(ValueError):p.validate_input(v)
    def test_partial_readback_and_unknown_field_rejected(self):
        for mutate in (lambda r:r['review']['settings']['trigger'].pop('events'),
                       lambda r:r['owner_resume'].update(settings_verified=True),
                       lambda r:r.update(unknown=True)):
            v,r,f=fixture('PRE_MERGE');mutate(r)
            with self.assertRaises(ValueError):p.resume(p.new_state(v),f,T0)
    def test_role_identity_and_owner_binding(self):
        for key,val in [('owner',{'login':'other','id':1,'type':'User'}),('issue',96),('purpose','other'),('input_digest','a'*64)]:
            v,r,f=fixture('PRE_MERGE');r[key]=val
            with self.assertRaises(ValueError):p.resume(p.new_state(v),f,T0)
        v,r,f=fixture('PRE_MERGE');r['owner_resume']['id']=v['work_automation_id']
        with self.assertRaises(ValueError):p.resume(p.new_state(v),f,T0)
    def test_negative_old_positive_twice_after_save_reload(self):
        v,r,f=fixture('PRE_MERGE');s=p.resume(p.new_state(v),f,T0)
        positive=copy.deepcopy(f)
        r['observed_at']=T1;r['owner_resume'].update(observed_at=T1);r['owner_resume']['settings']['enabled']=False
        s=p.resume(s,f,T1);s=p.loads(p.canonical(s))
        for _ in range(2):
            s=p.resume(s,positive,T2)
            self.assertEqual(s['status'],'WAITING')
            self.assertFalse(s['owner_watermarks']['owner_resume']['record']['settings']['enabled'])
    def test_mixed_negative_retained_and_same_time_conflict_barrier(self):
        v,r,f=fixture('PRE_MERGE');s=p.resume(p.new_state(v),f,T0)
        r['observed_at']=T1;r['review']['observed_at']=T1;s=p.resume(s,f,T1)
        r['review']['observed_at']=T0;r['owner_resume']['observed_at']=T1;r['owner_resume']['settings']['enabled']=False
        s=p.resume(s,f,T1)
        self.assertFalse(s['owner_watermarks']['owner_resume']['record']['settings']['enabled'])
        r['owner_resume']['settings']['enabled']=True
        s=p.resume(s,f,T1)
        self.assertEqual(s['status'],'WAITING')
        self.assertEqual(s['owner_watermarks']['owner_resume']['conflict_at'],T1)
    def test_api_failure_keeps_new_negative(self):
        v,r,f=fixture('PRE_MERGE');s=p.resume(p.new_state(v),f,T0)
        r['owner_resume'].update(status='UNKNOWN',observed_at=T1);r['observed_at']=T1
        out=p.resume(s,{'input_digest':p.digest(v),'owner_record':r,'fetch_error':True},T1)
        self.assertEqual(out['owner_watermarks']['owner_resume']['record']['status'],'UNKNOWN')
        self.assertEqual(out['status'],'WAITING')
        with self.assertRaises(ValueError):p.mark_unknown(out,'owner_resume')
    def test_settings_revision_and_head_rebinding(self):
        v,r,f=fixture('PRE_MERGE');s=p.resume(p.new_state(v),f,T0)
        r['owner_resume']['settings']['enabled']=False;r['owner_resume']['observed_at']=T1;r['observed_at']=T1
        s=p.resume(s,f,T1)
        r['owner_resume']['settings']['enabled']=True;r['owner_resume']['observed_at']=T2;r['observed_at']=T2
        s=p.resume(s,f,T2);self.assertEqual(s['status'],'WAITING')
        revised=copy.deepcopy(v);revised.update(input_version=2,head_sha='c'*40)
        out=p.rebase(s,revised)
        self.assertEqual(out['owner_watermarks'],s['owner_watermarks'])
        with self.assertRaises(ValueError):p.resume(out,f,T2)
    def test_unknown_and_attempting_no_recreation_across_input_changes(self):
        for status in ('UNKNOWN','ATTEMPTING'):
            v,r,f=fixture('PR_BOUND');r['owner_resume'].update(status=status,settings=None)
            s=p.resume(p.new_state(v),f,T0)
            with self.assertRaises(ValueError):p.mark_unknown(s,'owner_resume')
            v2=copy.deepcopy(v);v2['input_version']+=1
            s=p.rebase(s,v2)
            with self.assertRaises(ValueError):p.mark_unknown(s,'owner_resume')
            self.assertEqual(s['status'],'WAITING')
    def test_migration_retains_v1_unknown_and_rejects_mixed_contract(self):
        v,r,f=fixture();old=e.legacy_input(v);old['input_version']=1
        s=p.mark_unknown(p.new_state(old),'implementation_task')
        v['input_version']=2
        migrated=p.rebase(s,v)
        self.assertEqual(migrated['legacy']['operations'],s['operations'])
        self.assertEqual(migrated['input_history'],[old])
        with self.assertRaises(ValueError):p.validate_state({**migrated,'schema_version':1})
        body=e.REQUEST_START+'{}'+p.REQUEST_END+p.REQUEST_START+'{}'+p.REQUEST_END
        with self.assertRaises(ValueError):g.request_version(body)
    def test_observation_time_is_not_progress(self):
        v,r,f=fixture('PRE_MERGE');s=p.resume(p.new_state(v),f,T0)
        r['observed_at']=T1
        for role in e.ROLES:r[role]['observed_at']=T1
        out=p.resume(s,f,T1)
        self.assertEqual(out['last_progress_at'],T0)
        self.assertEqual(out['last_observed_at'],T0)
    def test_finished_needs_actual_stop_and_disabled_readback(self):
        v,r,f=fixture('FINISHED');out=p.resume(p.new_state(v),f,T0)
        self.assertEqual(out['status'],'WAITING')
        self.assertTrue(any('stop' in m for m in out['phase_evidence']['missing']))


class WriterV2Tests(unittest.TestCase):
    def test_same_owner_record_update_noop_and_prose_preserved(self):
        v,r,f,api=writer_api()
        self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T0),'UPDATED')
        self.assertIn('Human before',api.comment['body']);self.assertIn('Human after',api.comment['body'])
        self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T1),'NO_OP')
        self.assertEqual(len(api.writes),1)
        saved=g.snapshot(api.comment['body'])
        self.assertEqual(saved['schema_version'],2)
        self.assertEqual(saved['state']['phase_evidence']['i01_live'],'UNVERIFIED')
        r['review']['settings']['enabled']=False;r['review']['observed_at']=T1;r['observed_at']=T1
        new=p.generate(v,api.config,owner_facts=r)['github_record.md'].strip()
        start=api.comment['body'].index(e.REQUEST_START);end=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=api.comment['body'][:start]+new+api.comment['body'][end:]
        self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T1),'UPDATED')
        self.assertTrue(any(m.startswith('review:') for m in g.snapshot(api.comment['body'])['state']['phase_evidence']['missing']))
    def test_confirmed_state_generate_owner_request_same_comment_writer_roundtrip(self):
        from tools.automation_dashboard import render
        v,r,f,api=writer_api('PR_BOUND')
        api.pull=dict(number=89,head={'sha':HEAD},base={'ref':'main','repo':{'full_name':v['repository']}},body='Refs #100',merged=False)
        api.extra=[dict(id=123,user=v['owner'],body=render(initial_state(100,p.policy_entry(v))))]
        g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        state=g.snapshot(api.comment['body'])['state']
        self.assertTrue(state['operations'])
        self.assertTrue(all(o['status']=='SETTINGS_CONFIRMED' for o in state['operations'].values()))
        generated=p.generate(v,api.config,state=state,owner_facts=r)['github_record.md'].strip()
        request=g.block(generated,e.REQUEST_START,p.REQUEST_END)
        self.assertTrue(all(o['status']=='UNKNOWN' and o['external_id'] is None for o in request['operations'].values()))
        start=api.comment['body'].index(e.REQUEST_START);end=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=api.comment['body'][:start]+generated+api.comment['body'][end:]
        g.authenticate_comment(api.comment,100,p.policy_entry(v))
        g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        after=g.snapshot(api.comment['body'])['state']
        self.assertEqual(after['operations'],state['operations'])
        self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T1),'NO_OP')
        r['owner_resume'].update(status='UNKNOWN',observed_at=T1);r['observed_at']=T1
        generated=p.generate(v,api.config,state=after,owner_facts=r)['github_record.md'].strip()
        start=api.comment['body'].index(e.REQUEST_START);end=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=api.comment['body'][:start]+generated+api.comment['body'][end:]
        g.reconcile_preparation(api,100,p.policy_entry(v),T1)
        unknown=g.snapshot(api.comment['body'])['state']
        self.assertEqual(unknown['operations'][e.op_key(v,'owner_resume')]['status'],'UNKNOWN')
        with self.assertRaises(ValueError):p.mark_unknown(unknown,'owner_resume')

    def test_same_comment_negative_refresh_saved_even_when_progress_noop(self):
        v,r,f,api=writer_api();r['review']['settings']['enabled']=False
        t3='2026-10-08T03:03:00Z'
        def update(at,enabled=False,revision=1):
            r['observed_at']=at;r['review'].update(observed_at=at,settings_version=revision)
            r['review']['settings']['enabled']=enabled
            request=p.generate(v,api.config,owner_facts=r)['github_record.md'].strip()
            if e.REQUEST_START in api.comment['body']:
                a=api.comment['body'].index(e.REQUEST_START);b=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
                api.comment['body']=api.comment['body'][:a]+request+api.comment['body'][b:]
            return g.reconcile_preparation(api,100,p.policy_entry(v),at)
        update(T1);initial=g.snapshot(api.comment['body'])['state'];writes=len(api.writes)
        self.assertEqual(update(t3),'NO_OP');self.assertEqual(len(api.writes),writes+1)
        saved=p.loads(p.canonical(g.snapshot(api.comment['body'])['state']))
        self.assertEqual(saved['last_progress_at'],initial['last_progress_at'])
        self.assertEqual(saved['owner_watermarks']['review']['record']['observed_at'],t3)
        for _ in range(2):
            update(T2,True,2);saved=g.snapshot(api.comment['body'])['state']
            self.assertEqual(saved['status'],'WAITING')
            self.assertFalse(saved['owner_watermarks']['review']['record']['settings']['enabled'])
            self.assertEqual(saved['owner_watermarks']['review']['record']['observed_at'],t3)
    def test_same_comment_unresolved_reset_and_closed_review_remain_blocked(self):
        for pending in ('UNKNOWN','ATTEMPTING'):
            v,r,f,api=writer_api('PR_BOUND')
            r['owner_resume'].update(status=pending,id=None,settings=None,settings_version=None)
            def update(record,state=None):
                request=p.generate(v,api.config,state=state,owner_facts=record)['github_record.md'].strip()
                a=api.comment['body'].index(e.REQUEST_START);b=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
                api.comment['body']=api.comment['body'][:a]+request+api.comment['body'][b:]
                with patch.object(g,'current_preparation_facts',return_value={**f,'owner_record':record}):
                    g.reconcile_preparation(api,100,p.policy_entry(v),record['observed_at'])
                return g.snapshot(api.comment['body'])['state']
            state=update(r);key=e.op_key(v,'owner_resume')
            self.assertEqual(state['operations'][key]['status'],pending)
            r['observed_at']=T1;r['owner_resume'].update(status='NOT_ATTEMPTED',observed_at=T1)
            state=p.loads(p.canonical(update(r,state)))
            self.assertEqual(state['operations'][key]['status'],pending)
            changed=copy.deepcopy(v);changed.update(input_version=2,pr=90,head_sha='c'*40)
            with self.assertRaises(ValueError):p.mark_unknown(p.rebase(state,changed),'owner_resume')
        v,r,f,api=writer_api('PRE_MERGE');r['review']['settings']['trigger']['events']=['closed']
        request=p.generate(v,api.config,owner_facts=r)['github_record.md'].strip()
        a=api.comment['body'].index(e.REQUEST_START);b=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=api.comment['body'][:a]+request+api.comment['body'][b:]
        with patch.object(g,'current_preparation_facts',return_value=f):
            g.reconcile_preparation(api,100,p.policy_entry(v),T0)
            gate=g.collect_preparation_gate(api,100,p.policy_entry(v))
        self.assertEqual(gate['status'],'WAITING');self.assertTrue(any('review:' in m for m in gate['missing']))
    def test_writer_author_and_snapshot_version_rejected(self):
        v,r,f,api=writer_api();api.comment['user']={'login':'other','id':1,'type':'User'}
        with self.assertRaises(ValueError):g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        self.assertEqual(api.writes,[])
        v,r,f,api=writer_api();api.comment['body']+=p.REQUEST_START+'{}'+p.REQUEST_END
        with self.assertRaises(ValueError):g.reconcile_preparation(api,100,p.policy_entry(v),T0)
    def test_comment_race_no_write(self):
        v,r,f,api=writer_api()
        api.hook=lambda suffix:api.comment.update(body=api.comment['body']+'Concurrent prose') if suffix=='/issues/comments/100' else None
        with self.assertRaises(ValueError):g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        self.assertEqual(api.writes,[])
    def test_api_failure_negative_persisted_in_same_comment(self):
        v,r,f,api=writer_api();g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        r['review'].update(status='UNKNOWN',observed_at=T1);r['observed_at']=T1
        body=p.generate(v,api.config,owner_facts=r)['github_record.md'].strip()
        start=api.comment['body'].index(e.REQUEST_START);end=api.comment['body'].index(p.REQUEST_END)+len(p.REQUEST_END)
        api.comment['body']=api.comment['body'][:start]+body+api.comment['body'][end:]
        original=api.get
        def failed(suffix):
            if suffix=='/git/ref/heads/main':raise OSError('synthetic read failure')
            return original(suffix)
        api.get=failed
        with self.assertRaises(ValueError):g.reconcile_preparation(api,100,p.policy_entry(v),T1)
        saved=g.snapshot(api.comment['body'])['state']
        self.assertEqual(saved['status'],'WAITING')
        self.assertEqual(saved['owner_watermarks']['review']['record']['status'],'UNKNOWN')
    def test_unsupported_reader_and_v1_policy_do_not_accept_v2(self):
        v,r,f,api=writer_api();policy=p.policy_entry(e.legacy_input(v))
        with self.assertRaises(ValueError):g.reconcile_preparation(api,100,policy,T0)
        policy=p.policy_entry(v);policy['preparation_contract']=3
        with self.assertRaises(ValueError):g.collect_preparation_gate(api,100,policy)
    def test_ambiguous_write_then_noop_reconcile(self):
        v,r,f,api=writer_api();api.fail=OSError('synthetic response unknown')
        with self.assertRaises(g.PreparationWriteUnknown):g.reconcile_preparation(api,100,p.policy_entry(v),T0)
        api.fail=None
        self.assertEqual(g.reconcile_preparation(api,100,p.policy_entry(v),T0),'NO_OP')


class CLIV2Tests(unittest.TestCase):
    def test_documented_subprocess_utf8_exit_save_reload(self):
        v,r,f=fixture();config={'schema_version':1,'repository':v['repository'],'issues':{}}
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            for name,item in [('input',v),('owner',r),('config',config)]:
                (d/(name+'.json')).write_text(p.canonical(item),encoding='utf-8')
            cmd=[sys.executable,'-B',str(ROOT/'tools/startup_preparation.py'),'--input',str(d/'input.json'),
                 '--state',str(d/'state.json'),'--output',str(d/'out'),'--config',str(d/'config.json'),'--owner-facts',str(d/'owner.json')]
            first=subprocess.run(cmd,capture_output=True,cwd=ROOT)
            self.assertEqual(first.returncode,0,first.stderr.decode('utf-8'))
            self.assertIn('期限保証不能',first.stdout.decode('utf-8'))
            state=p.validate_state(p.loads((d/'state.json').read_text(encoding='utf-8')))
            self.assertEqual(state['status'],'WAITING') # local file cannot authenticate public Issue/policy/Dashboard
            second=subprocess.run(cmd,capture_output=True,cwd=ROOT)
            self.assertEqual(second.returncode,0,second.stderr.decode('utf-8'))
            self.assertIn('日本語',(d/'out/review_registration.md').read_text(encoding='utf-8'))
            r['input_digest']='a'*64;(d/'owner.json').write_text(p.canonical(r),encoding='utf-8')
            bad=subprocess.run(cmd,capture_output=True,cwd=ROOT)
            self.assertNotEqual(bad.returncode,0)
            self.assertEqual(state,p.loads((d/'state.json').read_text(encoding='utf-8')))
    def test_cli_explicit_migration_required_and_unknown_survives(self):
        v,r,f=fixture();old=e.legacy_input(v);v['input_version']=2
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);state=p.mark_unknown(p.new_state(old),'implementation_task')
            p.atomic_save(d/'state.json',state)
            (d/'input.json').write_text(p.canonical(v),encoding='utf-8')
            cmd=[sys.executable,'-B',str(ROOT/'tools/startup_preparation.py'),'--input',str(d/'input.json'),
                 '--state',str(d/'state.json'),'--output',str(d/'out'),'--config',str(d/'config.json')]
            (d/'config.json').write_text(p.canonical({'schema_version':1,'repository':v['repository'],'issues':{}}),encoding='utf-8')
            self.assertNotEqual(subprocess.run(cmd,capture_output=True,cwd=ROOT).returncode,0)
            self.assertEqual(state,p.loads((d/'state.json').read_text(encoding='utf-8')))
            result=subprocess.run(cmd+['--migrate-v2'],capture_output=True,cwd=ROOT)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            self.assertEqual(p.loads((d/'state.json').read_text(encoding='utf-8'))['legacy']['operations'],state['operations'])


class ScopedGateTests(unittest.TestCase):
    def test_old_gate_unchanged_and_optin_cannot_reuse_pass(self):
        policy,facts,report=fixtures();issue=80
        baseline=evaluate(issue,policy,None,facts)
        policy=copy.deepcopy(policy);policy['preparation_contract']=2
        out=evaluate(issue,policy,None,facts)
        self.assertEqual(out['merge_gate']['status'],'BLOCKED')
        self.assertNotEqual(out['merge_gate'],baseline['merge_gate'])
        self.assertEqual(evaluate(issue,{k:v for k,v in policy.items() if k!='preparation_contract'},None,facts),baseline)
    def test_scoped_gate_current_head_and_missing_preparation_veto(self):
        policy,facts,report=fixtures();issue=80;policy['preparation_contract']=2
        facts['preparation_gate']=dict(contract=2,pr=facts['pr']['number'],head_sha=HEAD,phase='PRE_MERGE',
                                       status='PHASE_EVIDENCE_COMPLETE',missing=[],i01_live='UNVERIFIED')
        for key,value in [('head_sha','c'*40),('phase','PR_BOUND'),('status','WAITING'),('missing',['disabled'])]:
            f=copy.deepcopy(facts);f['preparation_gate'][key]=value
            self.assertEqual(evaluate(issue,policy,None,f)['merge_gate']['status'],'BLOCKED')


class PostMergeCollectorTests(unittest.TestCase):
    def execution_api(self):
        from tools import work_owner_resume as w
        from tools.update_automation_dashboard import GitHub
        from tests.test_work_owner_resume import fixture as resume_fixture
        from tests.test_automation_dashboard import render, run
        v,r,f=fixture('POST_MERGE');execution,rf=resume_fixture()
        execution.update(issue=100,pr=89)
        execution['work']['automation_id']=v['owner_resume_id']
        execution['event']['pr']=89
        execution['waiting_record']={k:r['waiting_record'][k] for k in ('comment_id','body_sha256')}
        for field in ('claim','next_action'):execution[field]['dedup_key']=w.key(execution)
        execution['receipt'].update(waiting_comment_id=777,waiting_body_sha256=r['waiting_record']['body_sha256'])
        execution['next_action']['authorization_ref']=r['waiting_record']['authorization_ref']
        r['execution']=execution
        r['completion_observation']=dict(dashboard_comment_id=123,merge_sha=execution['merge_sha'],observed_at=T0,missing=['Synthetic current formal conditions'],evidence_ref='synthetic://remaining-conditions')
        rf['policy']=p.policy_entry(v);rf['issue'].update(number=100)
        rf['pr'].update(number=89,body='Refs #100\nCurrent head: '+HEAD,title='Issue #100: synthetic',state='closed',draft=False)
        review=p.loads(rf['pr_comments'][0]['body'].split('\n')[1]);review.update(issue=100,pr=89,automation_id=v['work_automation_id'])
        rf['pr_comments'][0]['body']='<!-- langbench-work-review:v1\n'+p.canonical(review)+'\n-->'
        rf['sync_reports']['20']['pr']=89
        rf['issue_comments']=f['issue_comments']+[dict(id=778,user=v['owner'],body=w.CLAIM_START+p.canonical(execution['claim'])+w.CLAIM_END)]
        rf['workflow_ids'].update({'python-tests.yml':1,'measurement-validation-windows.yml':3,'function-call-analysis-windows.yml':4})
        ci,jobs=run(10,'python-tests.yml',1);ci['pull_requests']=[{'number':89}]
        rf.update(ci_runs=[ci],reviews=[],condition_runs={},condition_artifacts={},result_pr=None,dashboard_comment_id=123)
        rf['jobs']['10']=jobs
        state=initial_state(100,rf['policy'])
        dashboard=dict(id=123,user=v['owner'],body=render(state))
        request=dict(id=100,user=v['owner'],body=p.generate(v,{'schema_version':2,'repository':v['repository'],'issues':{'100':rf['policy']}},owner_facts=r)['github_record.md'],
                     issue_url=f'https://api.github.com/repos/{v["repository"]}/issues/100',updated_at=T0)
        rf['issue_comments'] += [dashboard, request]
        class API(GitHub):
            def __init__(self):super().__init__('synthetic');self.reads=0
            def get(self,suffix):
                import base64
                self.reads+=1
                if self.reads>150:raise AssertionError('Recursive preparation collection')
                if suffix=='/branches/main':return {'commit':{'sha':rf['main_sha']}}
                if suffix=='/git/ref/heads/main':return {'object':{'sha':rf['main_sha']}}
                if suffix.startswith('/contents/'):return {'encoding':'base64','content':base64.b64encode(p.canonical({'schema_version':2,'repository':v['repository'],'issues':{'100':rf['policy']}}).encode()).decode()}
                if suffix=='/issues/100':return copy.deepcopy(rf['issue'])
                if suffix=='/pulls/89':return copy.deepcopy(rf['pr'])
                if suffix=='/issues/comments/100':return copy.deepcopy(request)
                raise AssertionError(suffix)
            def pages(self,suffix,key=None):
                if suffix.startswith('/issues/100/comments'):return copy.deepcopy(rf['issue_comments'])
                if suffix.startswith('/issues/89/comments'):return copy.deepcopy(rf['pr_comments'])
                if suffix.startswith('/pulls/89/reviews'):return []
                if suffix.startswith('/pulls?'):return [copy.deepcopy(rf['pr'])]
                if suffix=='/actions/workflows':return [{'id':i,'path':'.github/workflows/'+name,'state':'active'} for name,i in rf['workflow_ids'].items()]
                if suffix.startswith('/actions/workflows/python-tests.yml/runs'):return copy.deepcopy(rf['ci_runs'])
                if suffix.startswith('/actions/workflows/pull-local-main.yml/runs'):return copy.deepcopy(rf['sync_runs'])
                if suffix.startswith('/actions/runs/') and suffix.endswith('/jobs'):return copy.deepcopy(rf['jobs'][suffix.split('/')[3]])
                raise AssertionError(suffix)
            def sync_report(self,run):
                self.sync_artifacts=copy.deepcopy(rf['sync_artifacts'])
                return copy.deepcopy(rf['sync_reports'][str(run['id'])])
            def request(self,path,method='GET',data=None,raw=False):
                if method!='GET':raise AssertionError('Collector must not mutate')
                return self.get(path.removeprefix(self.root))
        return v,r,rf,API()
    def test_real_execution_shape_through_formal_collector_no_recursive_gate(self):
        from tools.update_automation_dashboard import collect
        v,r,rf,api=self.execution_api()
        _,facts=collect(api,100,rf['policy'],None)
        prepared=facts['preparation_gate']
        self.assertEqual(prepared['status'],'PHASE_EVIDENCE_COMPLETE',prepared['missing'])
        self.assertEqual(prepared['i01_live'],'OWNER_OBSERVED')
        self.assertLess(api.reads,150)
        evaluated=evaluate(100,rf['policy'],None,facts)
        self.assertNotEqual(evaluated['completion_gate']['status'],'PASS') # real implementation receipt and live smoke still missing
    def test_safe_stop_observed_does_not_promote_i01_or_completion(self):
        from tools import work_owner_resume as w
        v,r,rf,api=self.execution_api()
        r['waiting_record']['allowed_action']='safe_stop'
        r['execution']['next_action']['kind']='safe_stop'
        self.assertEqual(w.observe(r['execution'],rf)['status'],'OBSERVED')
        request=next(c for c in rf['issue_comments'] if c['id']==100)
        request['body']=p.generate(v,{'schema_version':2,'repository':v['repository'],'issues':{'100':rf['policy']}},owner_facts=r)['github_record.md']
        prepared=g.collect_preparation_gate(api,100,rf['policy'])
        self.assertEqual(prepared['status'],'WAITING')
        self.assertEqual(prepared['i01_live'],'UNVERIFIED')
        self.assertTrue(any('safe_stop' in m for m in prepared['missing']))
        for phase in ('POST_MERGE','FINISHED'):
            facts=copy.deepcopy(rf);facts['preparation_gate']={**prepared,'phase':phase}
            self.assertNotEqual(evaluate(100,rf['policy'],None,facts)['completion_gate']['status'],'PASS')

    def test_postmerge_claim_before_receipt_required_and_no_next_action(self):
        for mutate in (lambda r:r['execution'].update(next_action=None),
                       lambda r:r['execution']['receipt'].update(observed_at='2026-10-08T00:00:00Z')):
            v,r,rf,api=self.execution_api();mutate(r)
            # Replace the authenticated input; no made-up live event is published.
            request=next(c for c in rf['issue_comments'] if c['id']==100)
            request['body']=p.generate(v,{'schema_version':2,'repository':v['repository'],'issues':{'100':rf['policy']}},owner_facts=r)['github_record.md']
            prepared=g.collect_preparation_gate(api,100,rf['policy'])
            self.assertEqual(prepared['status'],'WAITING')
            self.assertEqual(prepared['i01_live'],'UNVERIFIED')
