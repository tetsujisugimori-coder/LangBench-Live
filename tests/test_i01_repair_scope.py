"""Synthetic Issue102 connection tests; not live Work or merge evidence."""
import copy
import unittest
from unittest.mock import patch

from tools import preparation_evidence as e, preparation_github as g
from tools import startup_preparation as p, work_owner_resume as w, work_resume_claim as c
from tests.test_preparation_evidence import fixture, T0, T1, T2
from tests.test_startup_preparation import PreparationAPI
from tests.test_work_resume_claim import capability_fixture, SECRET, RefAPI

PURPOSE = 'work-owner-resume-i01-repair'


def repair_input():
    value, owner, _ = fixture('PR_BOUND')
    value.update(issue=102, purpose=PURPOSE, pr=103)
    owner.update(issue=102, purpose=PURPOSE, input_digest=p.digest(value))
    for role in e.ROLES:
        owner[role]['settings']['trigger']['pr'] = 103
    return value, owner


def repair_execution():
    value, facts = capability_fixture()
    value.update(issue=102, purpose=PURPOSE, pr=103)
    value['event']['pr'] = 103
    value['authorization']['authorization_ref'] = 'Issue102'
    value['next_action']['authorization_ref'] = 'Issue102'
    for field in ('claim', 'next_action'):
        value[field]['dedup_key'] = w.key(value)
    value['claim']['ref'] = c.reservation_ref(value)
    facts['issue'].update(number=102, body='purpose: ' + PURPOSE)
    facts['policy']['purpose'] = PURPOSE
    facts['pr'].update(number=103, body='Refs #102')
    report = p.loads(facts['pr_comments'][0]['body'].split('\n')[1])
    report.update(issue=102, pr=103)
    facts['pr_comments'][0]['body'] = '<!-- langbench-work-review:v1\n' + p.canonical(report) + '\n-->'
    facts['sync_reports']['20']['pr'] = 103
    facts['resume_authorization'] = copy.deepcopy(value['authorization'])
    facts['resume_reservation'].update(ref=value['claim']['ref'], record=c.binding(value))
    return value, facts


class RepairScopeTests(unittest.TestCase):
    def test_same_owner_request_authenticated_and_generated_policy_enables_v2(self):
        value, owner = repair_input()
        policy = p.policy_entry(value)
        self.assertEqual(policy['resume_protocol'], 2)
        api = PreparationAPI(value)
        api.comment['body'] = p.generate(value, api.config, owner_facts=owner)['github_record.md']
        request = g.authenticate_comment(api.comment, 102, policy, api.comment['id'])
        self.assertEqual(request['input'], value)
        self.assertEqual(request['owner_facts'], owner)
        self.assertTrue(e.ready(owner['review'], value, 'review'))
        changed = copy.deepcopy(policy)
        changed['purpose'] = w.PURPOSE
        with self.assertRaises(ValueError):
            g.authenticate_comment(api.comment, 102, changed)

    def test_observe_and_single_reservation_use_repair_scope(self):
        value, facts = repair_execution()
        observed = w.observe(value, facts)
        self.assertEqual(observed['status'], 'OBSERVED', observed['reason'])
        self.assertEqual(w.observe(value, facts, observed), observed)
        api, journal = RefAPI(), {}
        reserved = c.acquire(api, value, SECRET, journal, lambda state: None)
        self.assertEqual(reserved['record']['purpose'], PURPOSE)
        self.assertEqual(len(api.posts), 2)
        self.assertEqual(c.acquire(api, value, SECRET, journal, lambda state: None), reserved)
        self.assertEqual(len(api.posts), 2)
        stale = copy.deepcopy(facts)
        stale['policy']['purpose'] = w.PURPOSE
        self.assertEqual(w.observe(value, stale)['status'], 'STOPPED')
        legacy = copy.deepcopy(value)
        legacy.update(issue=100, purpose=w.PURPOSE)
        self.assertNotEqual(c.reservation_ref(legacy), c.reservation_ref(value))

    def test_repair_purpose_cannot_enable_other_issue_or_legacy_handoff(self):
        value, _ = repair_input()
        value['issue'] = 100
        with self.assertRaises(ValueError):
            p.validate_input(value)
        execution, _ = repair_execution()
        execution['issue'] = 100
        with self.assertRaises(ValueError):
            w.validate(execution)
        legacy, _ = repair_execution()
        legacy['schema_version'] = 1
        legacy.pop('authorization')
        with self.assertRaises(ValueError):
            w.validate(legacy)

    def test_old_inputs_keep_original_policy_and_handoff_behavior(self):
        original, _, _ = fixture('PR_BOUND')
        self.assertEqual(p.policy_entry(original)['resume_protocol'], 2)
        original['issue'] = 96
        self.assertNotIn('resume_protocol', p.policy_entry(original))
        execution, facts = capability_fixture()
        self.assertEqual(w.observe(execution, facts)['status'], 'OBSERVED')

    def test_writer_roundtrip_and_input_revision_keep_same_repair_record(self):
        value, owner = repair_input()
        api = PreparationAPI(value)
        api.comment['body'] = p.generate(value, api.config, owner_facts=owner)['github_record.md']
        facts = dict(input_digest=p.digest(value), owner_record=owner, main_sha=value['head_sha'],
                     main_policy=p.policy_entry(value),
                     issue=dict(number=102, repository=value['repository'], purpose=PURPOSE, owner=value['owner']),
                     dashboard=dict(repository=value['repository'], issue=102, purpose=PURPOSE, comment_id=999),
                     policy_pr=dict(number=103, head_sha=value['head_sha'], merged=False), issue_comments=[])
        with patch.object(g, 'current_preparation_facts', return_value=facts):
            self.assertEqual(g.reconcile_preparation(api, 102, p.policy_entry(value), T0), 'UPDATED')
            state = p.loads(p.canonical(g.snapshot(api.comment['body'])['state']))
            value['input_version'] += 1
            owner.update(input_version=value['input_version'], input_digest=p.digest(value), observed_at=T1)
            for role in e.ROLES:
                owner[role]['observed_at'] = T1
            facts.update(input_digest=p.digest(value), owner_record=owner)
            for at in (T1, T2):
                generated = p.generate(value, api.config, state=state, owner_facts=owner)['github_record.md']
                start = api.comment['body'].index(e.REQUEST_START)
                end = api.comment['body'].index(p.REQUEST_END) + len(p.REQUEST_END)
                api.comment['body'] = api.comment['body'][:start] + generated + api.comment['body'][end:]
                g.reconcile_preparation(api, 102, p.policy_entry(value), at)
                state = p.loads(p.canonical(g.snapshot(api.comment['body'])['state']))
                g.authenticate_comment(api.comment, 102, p.policy_entry(value), 100)
                self.assertEqual(state['input']['purpose'], PURPOSE)
                self.assertEqual(state['input_history'][0]['issue'], 102)
                self.assertFalse(any(op['status'] in e.UNRESOLVED for op in state['operations'].values()))
