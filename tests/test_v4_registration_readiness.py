"""V4.0 Stage 3B: advisory I-07/I-09 registration readiness only.

Synthetic fixtures, no real Work registration or writer effects.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import startup_preparation as p
from tests.test_startup_preparation import input_fixture, owner_facts
from tests.test_preparation_evidence import fixture as v2_fixture, T0, T1, T2

ROOT = Path(__file__).resolve().parents[1]


class RegistrationReadinessTests(unittest.TestCase):
    def test_v1_missing_evidence_and_resume_are_not_verified(self):
        v = input_fixture()
        r = p.registration_readiness(v)
        self.assertEqual(r['kind'], 'local_registration_readiness_advisory')
        self.assertFalse(r['formal_gate_authorized'])
        self.assertFalse(r['registration_performed'])
        self.assertFalse(r['work_service_run_verified'])
        self.assertEqual(r['roles']['review']['registered_id'], v['work_automation_id'])
        self.assertFalse(r['roles']['review']['owner_settings_matched'])
        self.assertEqual(r['roles']['owner_resume']['owner_reported_status'], 'NOT_REPRESENTED_IN_V1')
        self.assertIsNone(r['roles']['owner_resume']['registered_id'])

    def test_v1_owner_report_is_not_service_confirmation(self):
        v = input_fixture()
        report = p.registration_readiness(v, owner_facts(v))
        self.assertEqual(report['roles']['review']['owner_reported_status'], 'OWNER_ATTESTED_PARTIAL')
        self.assertTrue(report['roles']['review']['owner_reported_event'])
        self.assertFalse(report['roles']['review']['owner_settings_matched'])
        self.assertFalse(report['roles']['review']['service_run_verified'])

    def test_v2_both_roles_derive_from_one_approved_input(self):
        v, record, facts = v2_fixture('PR_BOUND')
        state = p.resume(p.new_state(v), facts, T0)
        report = p.registration_readiness(v, record, state)
        self.assertEqual(report['issue'], 100)
        self.assertEqual(report['pr'], 89)
        self.assertEqual(report['head_sha'], v['head_sha'])
        self.assertEqual(report['input_digest'], p.digest(v))
        self.assertEqual(set(report['roles']), {'review', 'owner_resume'})
        for role in ('review', 'owner_resume'):
            self.assertTrue(report['roles'][role]['owner_settings_matched'])
            self.assertTrue(report['roles'][role]['accepted_observation'])
            self.assertEqual(report['roles'][role]['approved_events'], v['registration_prompts'][role]['events'])
            self.assertEqual(report['roles'][role]['approved_prompt_digest'], v['registration_prompts'][role]['digest'])
            self.assertFalse(report['roles'][role]['service_run_verified'])

    def test_partial_readback_never_confirms_settings(self):
        v, record, facts = v2_fixture('PR_BOUND')
        partial = copy.deepcopy(record)
        partial['owner_resume'].update(status='REGISTERED', settings=None, settings_version=None)
        facts['owner_record'] = partial
        state = p.resume(p.new_state(v), facts, T0)
        report = p.registration_readiness(v, partial, state)
        self.assertEqual(report['roles']['owner_resume']['owner_reported_status'], 'REGISTERED')
        self.assertFalse(report['roles']['owner_resume']['owner_settings_matched'])
        self.assertTrue(report['roles']['review']['owner_settings_matched'])


    def test_prior_success_rejected_after_newer_disabled_readback(self):
        v, positive, facts = v2_fixture('PR_BOUND')
        state = p.resume(p.new_state(v), facts, T0)
        self.assertTrue(p.registration_readiness(v, positive, state)['roles']['review']['owner_settings_matched'])
        negative = copy.deepcopy(positive)
        negative['observed_at'] = T1
        negative['review']['observed_at'] = T1
        negative['review']['settings_version'] = 2
        negative['review']['settings']['enabled'] = False
        later_facts = copy.deepcopy(facts)
        later_facts['owner_record'] = negative
        newer = p.resume(state, later_facts, T1)
        self.assertEqual(newer['status'], 'WAITING')
        rejected = p.resume(newer, facts, T2)
        self.assertEqual(rejected['status'], 'WAITING')
        self.assertTrue(any('older observation rejected' in reason
                            for reason in rejected['phase_evidence']['missing']))
        report = p.registration_readiness(v, positive, rejected)
        self.assertFalse(report['roles']['review']['accepted_observation'])
        self.assertFalse(report['roles']['review']['owner_settings_matched'])
        self.assertIn('do not reuse stale success', report['roles']['review']['next_action'])

    def test_finished_requires_disabled_readback_not_enabled_readback(self):
        v, record, facts = v2_fixture('FINISHED')
        initial = p.resume(p.new_state(v), facts, T0)
        running = p.registration_readiness(v, record, initial)
        for role in ('review', 'owner_resume'):
            self.assertTrue(running['roles'][role]['accepted_observation'])
            self.assertFalse(running['roles'][role]['owner_settings_matched'])
            self.assertIn('disabled', running['roles'][role]['next_action'])
        stopped = copy.deepcopy(record)
        stopped['observed_at'] = T1
        for role in ('review', 'owner_resume'):
            stopped[role]['status'] = 'DISABLED_CONFIRMED'
            stopped[role]['settings']['enabled'] = False
            stopped[role]['settings_version'] = 2
            stopped[role]['observed_at'] = T1
        latest = copy.deepcopy(facts)
        latest['owner_record'] = stopped
        finished = p.resume(initial, latest, T1)
        summary = p.registration_readiness(v, stopped, finished)
        for role in ('review', 'owner_resume'):
            self.assertTrue(summary['roles'][role]['accepted_observation'])
            self.assertTrue(summary['roles'][role]['owner_settings_matched'])
            self.assertIn('do not continue using this role', summary['roles'][role]['next_action'])

    def test_api_outage_never_turns_cached_positive_into_current_readiness(self):
        v, record, facts = v2_fixture('PR_BOUND')
        previous = p.resume(p.new_state(v), facts, T0)
        self.assertTrue(p.registration_readiness(v, record, previous)['roles']['review']['owner_settings_matched'])
        interrupted = p.resume(previous, {'input_digest': p.digest(v), 'fetch_error': True}, T1)
        self.assertEqual(interrupted['status'], 'WAITING')
        report = p.registration_readiness(v, record, interrupted)
        self.assertFalse(report['roles']['review']['accepted_observation'])
        self.assertFalse(report['roles']['review']['owner_settings_matched'])

    def test_unreconciled_raw_owner_data_is_not_ready(self):
        v, record, _ = v2_fixture('PR_BOUND')
        report = p.registration_readiness(v, record)
        self.assertFalse(report['roles']['review']['owner_settings_matched'])
        self.assertFalse(report['roles']['review']['accepted_observation'])
        self.assertIn('Reconcile current role observation', report['roles']['review']['next_action'])

    def test_binding_change_or_spoofed_facts_fail(self):
        v, record, _ = v2_fixture('PR_BOUND')
        changed = copy.deepcopy(v)
        changed['head_sha'] = 'c' * 40
        with self.assertRaises(ValueError):
            p.registration_readiness(changed, record)
        spoof = copy.deepcopy(record)
        spoof['review']['id'] = 'f' * 32
        with self.assertRaises(ValueError):
            p.registration_readiness(v, spoof)

    def test_cli_opt_in_writes_local_report_without_default_output_change(self):
        v = input_fixture()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / 'input.json').write_text(p.canonical(v), encoding='utf-8')
            (d / 'policy.json').write_text(p.canonical({
                'schema_version': 1, 'repository': v['repository'], 'issues': {}}), encoding='utf-8')
            cmd = [sys.executable, '-B', str(ROOT / 'tools/startup_preparation.py'),
                   '--input', str(d / 'input.json'), '--config', str(d / 'policy.json'),
                   '--state', str(d / 'cache.json'), '--output', str(d / 'out')]
            first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertFalse((d/'out/registration_readiness.json').exists())
            second = subprocess.run(cmd + ['--registration-readiness'], cwd=ROOT,
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(second.returncode, 0, second.stderr)
            actual = json.loads((d/'out/registration_readiness.json').read_text(encoding='utf-8'))
            self.assertEqual(actual, p.registration_readiness(v))
            self.assertFalse(actual['formal_gate_authorized'])
            self.assertTrue((d/'out/github_record.md').exists())


    def test_old_report_survives_failed_run_but_exit_is_not_success(self):
        """A stale local file is never proof that the current run succeeded."""
        v = input_fixture()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            input_path = d / 'input.json'
            input_path.write_text(p.canonical(v), encoding='utf-8')
            config_path = d / 'config.json'
            config_path.write_text(p.canonical({
                'schema_version': 1, 'repository': v['repository'], 'issues': {}}),
                encoding='utf-8')
            cmd = [sys.executable, '-B', str(ROOT / 'tools/startup_preparation.py'),
                   '--input', str(input_path), '--config', str(config_path),
                   '--state', str(d / 'state.json'), '--output', str(d / 'out'),
                   '--registration-readiness']
            first = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                   text=True, encoding='utf-8')
            self.assertEqual(first.returncode, 0, first.stderr)
            result_path = d / 'out' / 'registration_readiness.json'
            retained = result_path.read_bytes()
            self.assertTrue(retained)

            # Invalid input fails before normal output generation, leaving the
            # preceding report intact. The consumer must obey the new exit status.
            invalid = copy.deepcopy(v)
            invalid['repository'] = 'not-the-authorized-repository'
            input_path.write_text(p.canonical(invalid), encoding='utf-8')
            failed = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                    text=True, encoding='utf-8')
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(result_path.read_bytes(), retained)




if __name__ == '__main__':
    unittest.main()
