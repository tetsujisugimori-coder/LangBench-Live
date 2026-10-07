"""Issue #91 REST-shape regression through the formal preparation writer."""
import copy
import unittest

from tools import startup_preparation as p
from tools.preparation_github import (reconcile_preparation, snapshot,
                                     PreparationConflict, PreparationWriteUnknown)
from tests.test_startup_preparation import PreparationAPI, input_fixture
from tests.test_automation_dashboard import NOW


class RestShapeAPI(PreparationAPI):
    """Model the observed list/single performed_via_github_app difference."""
    def pages(self, suffix, key=None):
        comments = super().pages(suffix, key)
        if suffix.startswith('/issues/'):
            for comment in comments:
                comment['performed_via_github_app'] = None
        return comments

    def get(self, suffix):
        result = super().get(suffix)
        if suffix.startswith('/issues/comments/'):
            result['performed_via_github_app'] = {'id': 123, 'slug': 'synthetic-app'}
            result['extra_metadata'] = {'synthetic': True}
            result['user']['avatar_url'] = 'https://example.invalid/synthetic-avatar'
        return result


class CommentConflict(unittest.TestCase):
    def setUp(self):
        self.value = input_fixture()
        self.api = RestShapeAPI(self.value)
        self.policy = p.policy_entry(self.value)

    def update(self, now=NOW):
        return reconcile_preparation(self.api, 88, self.policy, now)

    def test_observed_metadata_difference_updates_same_record_then_noop(self):
        original = self.api.comment['body']
        self.assertEqual('UPDATED', self.update())
        self.assertTrue(self.api.comment['body'].startswith(original))
        saved = copy.deepcopy(snapshot(self.api.comment['body']))
        self.assertEqual('NO_OP', self.update('2026-10-08T00:00:00Z'))
        self.assertEqual(saved, snapshot(self.api.comment['body']))
        self.assertEqual(1, len(self.api.writes))
        self.assertEqual(self.api.root + '/issues/comments/100', self.api.writes[0][0])

    def test_required_initial_fields_are_not_optional_metadata(self):
        for field in ('id', 'body', 'user', 'issue_url', 'updated_at'):
            with self.subTest(field=field):
                api = RestShapeAPI(self.value)
                api.comment.pop(field)
                with self.assertRaises(ValueError):
                    reconcile_preparation(api, 88, self.policy, NOW)
                self.assertEqual([], api.writes)

    def test_initial_id_types_and_target_are_strict(self):
        for field, value in (('id', '100'), ('id', True), ('id', 0), ('body', None),
                             ('issue_url', 'https://api.github.com/repos/other/repo/issues/88'),
                             ('updated_at', 'broken'), ('updated_at', None)):
            with self.subTest(field=field, value=value):
                api = RestShapeAPI(self.value)
                api.comment[field] = value
                with self.assertRaises((ValueError, TypeError)):
                    reconcile_preparation(api, 88, self.policy, NOW)
                self.assertEqual([], api.writes)

    def test_latest_target_author_fields_and_request_are_reauthenticated(self):
        def mutate(result, case):
            if case == 'missing-request': result['body'] = 'Human prose only'
            elif case == 'scope':
                result['body'] = result['body'].replace('"issue":88', '"issue":89')
            elif case == 'id': result['id'] = 101
            elif case == 'id-type': result['id'] = '100'
            elif case == 'owner': result['user']['login'] = 'other'
            elif case == 'author-id-type': result['user']['id'] = str(result['user']['id'])
            elif case == 'issue': result['issue_url'] = result['issue_url'].replace('/88', '/89')
            else: result.pop(case)
        for case in ('missing-request', 'scope', 'id', 'id-type', 'owner', 'author-id-type',
                     'issue', 'body', 'user', 'issue_url', 'updated_at'):
            with self.subTest(case=case):
                api = RestShapeAPI(self.value)
                original_get = api.get
                def get(path):
                    result = original_get(path)
                    if path == '/issues/comments/100': mutate(result, case)
                    return result
                api.get = get
                with self.assertRaises(ValueError):
                    reconcile_preparation(api, 88, self.policy, NOW)
                self.assertEqual([], api.writes)

    def test_exact_body_change_including_whitespace_and_snapshot_stops_patch(self):
        for case in ('human', 'whitespace', 'input', 'snapshot'):
            with self.subTest(case=case):
                api = RestShapeAPI(self.value)
                if case == 'snapshot':
                    reconcile_preparation(api, 88, self.policy, NOW)
                    api.writes.clear()
                old_get = api.get
                def get(path):
                    result = old_get(path)
                    if path == '/issues/comments/100':
                        if case == 'human': result['body'] += '\nConcurrent human note'
                        elif case == 'whitespace': result['body'] += ' '
                        elif case == 'input': result['body'] = result['body'].replace('"input_version":1', '"input_version":2')
                        else: result['body'] = result['body'].replace('"shared_persistence":true', '"shared_persistence":false')
                    return result
                api.get = get
                with self.assertRaises(PreparationConflict):
                    reconcile_preparation(api, 88, self.policy, NOW)
                self.assertEqual([], api.writes)

    def test_changed_update_time_requires_fresh_read_even_with_identical_body(self):
        def hook(path):
            if path == '/issues/comments/100':
                self.api.comment['updated_at'] = '2026-10-08T00:00:00Z'
        self.api.hook = hook
        with self.assertRaisesRegex(PreparationConflict, 'update information changed'):
            self.update()
        self.assertEqual([], self.api.writes)
        self.api.hook = None
        self.assertEqual('UPDATED', self.update())
        self.assertEqual('NO_OP', self.update())

    def test_actual_human_edit_is_retained_by_fresh_reconciliation(self):
        def hook(path):
            if path == '/issues/comments/100': self.api.comment['body'] += '\nHuman concurrent edit'
        self.api.hook = hook
        with self.assertRaises(PreparationConflict): self.update()
        self.assertEqual([], self.api.writes)
        latest = self.api.comment['body']
        self.api.hook = None
        self.assertEqual('UPDATED', self.update())
        self.assertTrue(self.api.comment['body'].startswith(latest))

    def test_external_facts_change_still_stops_write(self):
        count = 0
        def hook(path):
            nonlocal count
            if path == '/git/ref/heads/main':
                count += 1
                if count == 2: self.api.main_sha = 'd' * 40
        self.api.hook = hook
        with self.assertRaises(PreparationConflict): self.update()
        self.assertEqual([], self.api.writes)

    def test_patch_and_post_read_identity_author_body_mismatch_is_unknown(self):
        for stage in ('patch', 'checked'):
            for case in ('id', 'owner', 'scope', 'body', 'missing-user', 'issue-url'):
                with self.subTest(stage=stage, case=case):
                    api = RestShapeAPI(self.value)
                    old_get, old_request = api.get, api.request
                    def mutate(result):
                        if case == 'id': result['id'] = 101
                        elif case == 'owner': result['user']['login'] = 'other'
                        elif case == 'scope': result['body'] = result['body'].replace('"issue":88', '"issue":89')
                        elif case == 'body': result['body'] += '\nUnexpected post-write edit'
                        elif case == 'missing-user': result.pop('user')
                        else: result['issue_url'] = result['issue_url'].replace('/88', '/89')
                        return result
                    def get(path):
                        result = old_get(path)
                        return mutate(result) if stage == 'checked' and api.writes and path == '/issues/comments/100' else result
                    def request(path, method, data):
                        result = old_request(path, method, data)
                        return mutate(result) if stage == 'patch' else result
                    api.get, api.request = get, request
                    with self.assertRaises(PreparationWriteUnknown):
                        reconcile_preparation(api, 88, self.policy, NOW)
                    self.assertEqual(1, len(api.writes))

    def test_ambiguous_patch_inspects_saved_record_without_resending(self):
        self.api.fail = OSError('synthetic response lost after write')
        with self.assertRaises(PreparationWriteUnknown): self.update()
        self.assertEqual(1, len(self.api.writes))
        self.api.fail = None
        self.assertEqual('NO_OP', self.update())
        self.assertEqual(1, len(self.api.writes))


if __name__ == '__main__':
    unittest.main()
