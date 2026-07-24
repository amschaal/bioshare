"""
Security tests for the bioshareX backend: authentication requirements,
per-permission authorization boundaries, share state enforcement (secure /
read-only / locked), object-level scoping (IDOR), CSRF, and rate limiting.

Filesystem path/symlink traversal tests live in test_path_security.py;
happy-path endpoint behavior lives in test_api.py.

Run with:  python manage.py test bioshareX.test_api_security
"""

import json
import os

from django.contrib.auth.models import Group
from django.test import Client, override_settings
from django.urls import reverse

from bioshareX.models import Share, ShareLog, SSHKey
from bioshareX.test_base import AJAX, ShareTestBase

JSON = 'application/json'


class EndpointMatrixMixin(ShareTestBase):
    """Builds the list of protected endpoints for the fixture share."""

    def share_endpoints(self):
        """(label, method, url, post_data, content_type) for every endpoint
        that requires some permission on self.share."""
        s = {'share': self.share.id}
        return [
            ('list_directory', 'get', reverse('list_directory', kwargs=s), None, None),
            ('download_file', 'get',
             reverse('download_file', kwargs={**s, 'subpath': 'hello.txt'}), None, None),
            ('preview_file', 'get',
             reverse('preview_file', kwargs={**s, 'subpath': 'hello.txt'}), None, None),
            ('md5sum', 'get',
             reverse('md5sum', kwargs={**s, 'subpath': 'hello.txt'}), None, None),
            ('get_directories', 'get', reverse('get_directories', kwargs=s), None, None),
            ('wget_listing', 'get', reverse('wget_listing', kwargs=s), None, None),
            ('stream_archive', 'get',
             reverse('download_archive_stream', kwargs=s) + '?selection=hello.txt', None, None),
            ('search_share', 'get',
             reverse('api_search_share', kwargs=s) + '?query=hello', None, None),
            ('go_to_file', 'get',
             reverse('go_to_file_or_folder', kwargs={**s, 'subpath': 'hello.txt'}), None, None),
            ('get_permissions', 'get', reverse('api_get_permissions', kwargs=s), None, None),
            ('share_with', 'get',
             reverse('api_share_with', kwargs=s) + '?query=a@example.com', None, None),
            ('share_permissions', 'get', reverse('share_permissions', kwargs=s), None, None),
            ('view_links', 'get', reverse('view_links', kwargs=s), None, None),
            ('update_stats', 'get', reverse('update_stats', kwargs=s), None, None),
            ('edit_share', 'get', reverse('edit_share', kwargs=s), None, None),
            ('delete_share', 'get', reverse('delete_share', kwargs=s), None, None),
            ('confirm_delete_share', 'get',
             reverse('confirm_delete_share', kwargs=s), None, None),
            ('create_subshare', 'get',
             reverse('create_subshare', kwargs={**s, 'subdir': 'docs/'}), None, None),
            ('upload_file', 'post', reverse('upload_file', kwargs=s), {}, None),
            ('create_folder', 'post', reverse('create_folder', kwargs=s),
             {'name': 'x'}, None),
            ('modify_name', 'post', reverse('modify_name', kwargs=s),
             {'from_name': 'hello.txt', 'to_name': 'x.txt'}, None),
            ('delete_paths', 'post', reverse('delete_paths', kwargs=s),
             json.dumps({'selection': ['hello.txt']}), JSON),
            ('move_paths', 'post', reverse('move_paths', kwargs=s),
             json.dumps({'json': {'selection': ['hello.txt'], 'destination': 'docs'}}), JSON),
            ('set_permissions', 'post', reverse('api_set_permissions', kwargs=s),
             json.dumps({'json': {'users': {}, 'email': False}}), JSON),
            ('update_share', 'post', reverse('api_update_share', kwargs=s),
             json.dumps({'json': {'secure': False}}), JSON),
            ('edit_metadata', 'post',
             reverse('api_edit_metadata', kwargs={**s, 'subpath': 'hello.txt'}),
             {'notes': 'x', 'tags': ''}, None),
            ('email_participants', 'post',
             reverse('api_email_participants', kwargs={**s, 'subdir': ''}),
             {'subject': 'x', 'body': 'y'}, None),
            ('share_read_only', 'post', reverse('api_share_read_only', kwargs=s),
             json.dumps({'email': 'a@example.com'}), JSON),
        ]

    def auth_only_endpoints(self):
        """Endpoints that require authentication but no share permission."""
        return [
            ('get_user', 'get', reverse('api_get_user') + '?query=x', None, None),
            ('get_addresses', 'get', reverse('api_get_address_book'), None, None),
            ('get_tags', 'get', reverse('api_tags') + '?tag=x', None, None),
            ('get_group', 'get', reverse('api_get_group') + '?query=x', None, None),
            ('autocomplete', 'get',
             reverse('api_share_autocomplete') + '?query=x', None, None),
            ('delete_ssh_key', 'post', reverse('api_delete_ssh_key'), {'id': 1}, None),
            ('create_share_api', 'post', reverse('api_create_share'),
             json.dumps({'name': 'x'}), JSON),
            ('list_shares', 'get', reverse('list_shares'), None, None),
            ('create_share_web', 'get', reverse('create_share'), None, None),
            ('list_ssh_keys', 'get', reverse('list_ssh_keys'), None, None),
            ('manage_groups', 'get', reverse('groups'), None, None),
            ('drf_shares', 'get', '/bioshare/api/shares/', None, None),
            ('drf_share_detail', 'get', '/bioshare/api/shares/%s/' % self.share.id, None, None),
            ('drf_logs', 'get', '/bioshare/api/logs/', None, None),
            ('drf_groups', 'get', '/bioshare/api/groups/', None, None),
            ('drf_messages', 'get', '/bioshare/api/messages/', None, None),
        ]

    def request(self, method, url, data, content_type):
        kwargs = dict(AJAX)
        if content_type:
            return getattr(self.client, method)(url, data, content_type=content_type, **kwargs)
        if data is not None:
            return getattr(self.client, method)(url, data, **kwargs)
        return getattr(self.client, method)(url, **kwargs)


class TestAnonymousAccess(EndpointMatrixMixin):
    """No protected endpoint may serve an unauthenticated request."""

    def test_anonymous_is_denied_everywhere(self):
        for label, method, url, data, ctype in (self.share_endpoints() +
                                                self.auth_only_endpoints()):
            with self.subTest(endpoint=label):
                response = self.request(method, url, data, ctype)
                self.assertIn(response.status_code, (302, 400, 401, 403),
                              '%s returned %s' % (label, response.status_code))
                if response.status_code == 302:
                    # redirects must go to the login page, not leak content
                    self.assertIn('login', response['Location'])

    def test_anonymous_cannot_read_share_file_content(self):
        url = reverse('download_file',
                      kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url, **AJAX)
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(b'Hello bioshare!', getattr(response, 'content', b''))

    def test_anonymous_create_modify_group_creates_nothing(self):
        response = self.client.post(reverse('create_group'), {'name': 'sneaky'})
        self.assertFalse(Group.objects.filter(name='sneaky').exists())
        self.assertContains(response, 'forbidden')


class TestUserWithoutPermissions(EndpointMatrixMixin):
    """An authenticated user with no grants on a secure share is denied."""

    def test_share_endpoints_denied(self):
        self.login(self.other)
        for label, method, url, data, ctype in self.share_endpoints():
            with self.subTest(endpoint=label):
                response = self.request(method, url, data, ctype)
                self.assertNotEqual(response.status_code, 200,
                                    '%s allowed a user with no permissions' % label)
                self.assertLess(response.status_code, 500,
                                '%s crashed (%s)' % (label, response.status_code))
        # nothing was modified along the way
        self.share.refresh_from_db()
        self.assertTrue(self.share.secure)
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_non_staff_cannot_create_or_modify_groups(self):
        self.login(self.other)
        self.client.post(reverse('create_group'), {'name': 'sneaky'})
        self.assertFalse(Group.objects.filter(name='sneaky').exists())
        response = self.client.post(
            reverse('modify_group', kwargs={'group_id': self.group.id}),
            {'name': 'hijacked'})
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, 'testgroup')


class TestPermissionBoundaries(EndpointMatrixMixin):
    """Each permission level unlocks exactly its own operations."""

    def assert_denied(self, response, label=''):
        self.assertNotEqual(response.status_code, 200, label)
        self.assertLess(response.status_code, 500, label)

    def test_viewer_cannot_download_write_delete_or_admin(self):
        self.login(self.viewer)
        s = {'share': self.share.id}
        for label, method, url, data, ctype in self.share_endpoints():
            if label in ('list_directory', 'search_share', 'md5sum', 'go_to_file',
                         'email_participants'):
                continue  # granted by view_share_files (covered by functional tests)
            with self.subTest(endpoint=label):
                self.assert_denied(self.request(method, url, data, ctype), label)
        # sanity: view itself still works
        self.assertEqual(self.client.get(
            reverse('list_directory', kwargs=s), **AJAX).status_code, 200)

    def test_downloader_cannot_write_or_delete(self):
        self.login(self.downloader)
        s = {'share': self.share.id}
        for name, kwargs, data in (
                ('upload_file', s, {}),
                ('create_folder', s, {'name': 'x'}),
                ('modify_name', s, {'from_name': 'hello.txt', 'to_name': 'x.txt'})):
            self.assert_denied(self.client.post(reverse(name, kwargs=kwargs), data, **AJAX), name)
        self.assert_denied(self.client.post(
            reverse('delete_paths', kwargs=s), json.dumps({'selection': ['hello.txt']}),
            content_type=JSON, **AJAX), 'delete_paths')
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_writer_cannot_delete_download_or_admin(self):
        self.login(self.writer)
        s = {'share': self.share.id}
        self.assert_denied(self.client.post(
            reverse('delete_paths', kwargs=s), json.dumps({'selection': ['hello.txt']}),
            content_type=JSON, **AJAX), 'delete_paths')
        self.assert_denied(self.client.post(
            reverse('move_paths', kwargs=s),
            json.dumps({'json': {'selection': ['hello.txt'], 'destination': 'docs'}}),
            content_type=JSON, **AJAX), 'move_paths')
        self.assert_denied(self.client.get(reverse(
            'download_file', kwargs={**s, 'subpath': 'hello.txt'}), **AJAX), 'download')
        self.assert_denied(self.client.get(
            reverse('api_get_permissions', kwargs=s), **AJAX), 'get_permissions')
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_deleter_cannot_write(self):
        self.login(self.deleter)
        s = {'share': self.share.id}
        self.assert_denied(self.client.post(reverse('upload_file', kwargs=s), {}, **AJAX))
        self.assert_denied(self.client.post(
            reverse('create_folder', kwargs=s), {'name': 'x'}, **AJAX))
        self.assert_denied(self.client.post(
            reverse('modify_name', kwargs=s),
            {'from_name': 'hello.txt', 'to_name': 'x.txt'}, **AJAX))

    def test_admin_perm_grants_permission_management_but_not_files(self):
        self.login(self.sharer)  # holds only the 'admin' permission
        s = {'share': self.share.id}
        self.assertEqual(self.client.get(
            reverse('api_get_permissions', kwargs=s)).status_code, 200)
        response = self.client.post(reverse('api_update_share', kwargs=s),
                                    json.dumps({'json': {'secure': True}}),
                                    content_type=JSON)
        self.assertEqual(response.status_code, 200)
        self.assert_denied(self.client.get(
            reverse('list_directory', kwargs=s), **AJAX), 'list_directory')
        self.assert_denied(self.client.get(reverse(
            'download_file', kwargs={**s, 'subpath': 'hello.txt'}), **AJAX), 'download')

    def test_superuser_has_full_access(self):
        self.login(self.superuser)
        s = {'share': self.share.id}
        response = self.client.get(
            reverse('download_file', kwargs={**s, 'subpath': 'hello.txt'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(
            reverse('api_get_permissions', kwargs=s)).status_code, 200)

    def test_create_share_requires_add_share_permission(self):
        self.login(self.other)  # authenticated, no add_share
        response = self.client.post(reverse('api_create_share'), json.dumps({
            'name': 'Nope', 'filesystem': self.filesystem.id}), content_type=JSON)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Share.objects.filter(name='Nope').exists())

    def test_create_share_link_to_path_requires_permission(self):
        self.give_global_perm(self.owner, 'add_share')
        self.login(self.owner)  # has add_share but not link_to_path
        response = self.client.post(reverse('api_create_share'), json.dumps({
            'name': 'Linked', 'filesystem': self.filesystem.id,
            'link_to_path': self.fs_dir}), content_type=JSON)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Share.objects.filter(name='Linked').exists())

    def test_symlink_endpoints_require_link_permission(self):
        self.login(self.writer)  # write access but no link_to_path
        response = self.client.post(
            reverse('create_symlink', kwargs={'share': self.share.id}),
            json.dumps({'name': 'l', 'target': self.fs_dir}), content_type=JSON)
        self.assertEqual(response.status_code, 403)
        link = os.path.join(self.share.get_path(), 'reallink')
        os.symlink(self.fs_dir, link)
        response = self.client.get(
            reverse('unlink', kwargs={'share': self.share.id, 'subpath': 'reallink'}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(os.path.islink(link))

    def test_edit_share_denied_for_non_owner_admin(self):
        self.login(self.sharer)  # admin perm but not owner/superuser
        response = self.client.get(reverse('edit_share', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 403)

    def test_delete_share_denied_for_non_owner_admin(self):
        self.grant(self.sharer, Share.PERMISSION_ADMIN)
        self.login(self.sharer)
        self.client.get(reverse('confirm_delete_share', kwargs={'share': self.share.id}))
        self.assertTrue(Share.objects.filter(id=self.share.id).exists())


class TestShareStates(ShareTestBase):
    """secure=False, read_only, and locked shares enforce their semantics."""

    def make_open_share(self):
        share = self.make_share(self.owner, name='Open Share', secure=False)
        self.write_share_file('public.txt', b'public data\n', share=share)
        return share

    def test_open_share_readable_by_anyone(self):
        share = self.make_open_share()
        # authenticated user without grants
        self.login(self.other)
        response = self.client.get(reverse('list_directory', kwargs={'share': share.id}), **AJAX)
        self.assertEqual(response.status_code, 200)
        # anonymous
        self.client.logout()
        response = self.client.get(reverse('list_directory', kwargs={'share': share.id}), **AJAX)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse(
            'download_file', kwargs={'share': share.id, 'subpath': 'public.txt'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'public data\n')

    def test_open_share_still_blocks_writes(self):
        share = self.make_open_share()
        url = reverse('create_folder', kwargs={'share': share.id})
        self.login(self.other)
        self.assertNotEqual(self.client.post(url, {'name': 'x'}, **AJAX).status_code, 200)
        self.client.logout()
        self.assertNotEqual(self.client.post(url, {'name': 'x'}, **AJAX).status_code, 200)
        self.assertFalse(os.path.exists(os.path.join(share.get_path(), 'x')))

    def test_read_only_share_blocks_writes_even_for_owner(self):
        share = self.make_share(self.owner, name='RO Share', read_only=True)
        self.grant(self.writer, Share.PERMISSION_VIEW, Share.PERMISSION_WRITE, share=share)
        url = reverse('create_folder', kwargs={'share': share.id})
        for user in (self.writer, self.owner):
            self.login(user)
            response = self.client.post(url, {'name': 'x'}, **AJAX)
            self.assertNotEqual(response.status_code, 200, user.username)
        self.assertFalse(os.path.exists(os.path.join(share.get_path(), 'x')))

    def test_locked_share_denies_even_owner(self):
        self.share.locked = True
        self.share.save()
        self.login(self.owner)
        response = self.client.get(
            reverse('list_directory', kwargs={'share': self.share.id}), **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertIn('locked', self.json_of(response)['errors'][0])
        # non-ajax requests are redirected to the locked page
        response = self.client.get(reverse('list_directory', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/locked/', response['Location'])

    def test_unlock_requires_superuser(self):
        self.share.locked = True
        self.share.save()
        self.login(self.owner)
        with self.assertRaises(PermissionError):
            self.client.get(reverse('unlock', kwargs={'share': self.share.id}))
        self.share.refresh_from_db()
        self.assertTrue(self.share.locked)

    def test_superuser_can_unlock_clean_share(self):
        self.share.locked = True
        self.share.save()
        self.login(self.superuser)
        response = self.client.get(reverse('unlock', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 302)
        self.share.refresh_from_db()
        self.assertFalse(self.share.locked)


class TestObjectScoping(ShareTestBase):
    """Object-level scoping: users must not see or touch other users' objects."""

    def setUp(self):
        super().setUp()
        self.private_share = self.make_share(self.other, name='Private Share')
        self.write_share_file('secret.txt', b'top secret\n', share=self.private_share)
        ShareLog.create(share=self.private_share, user=self.other,
                        action=ShareLog.ACTION_FILE_ADDED, paths=['secret.txt'])

    def test_share_detail_hidden_from_non_participant(self):
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/%s/' % self.private_share.id)
        self.assertEqual(response.status_code, 404)

    def test_share_list_and_export_exclude_foreign_shares(self):
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/')
        self.assertNotIn(self.private_share.id,
                         [s['id'] for s in response.json()['results']])
        response = self.client.get('/bioshare/api/shares/export/')
        self.assertNotIn(self.private_share.id, response.content.decode())

    def test_directory_size_hidden_from_non_participant(self):
        self.login(self.viewer)
        response = self.client.get(
            '/bioshare/api/shares/%s/directory_size/' % self.private_share.id)
        self.assertEqual(response.status_code, 404)

    def test_logs_exclude_foreign_shares(self):
        ShareLog.create(share=self.share, user=self.owner,
                        action=ShareLog.ACTION_FILE_ADDED, paths=['hello.txt'])
        self.login(self.viewer)
        data = self.client.get('/bioshare/api/logs/').json()
        shares_seen = {log['share'] for log in data['results']}
        self.assertEqual(shares_seen, {self.share.id})
        # explicitly filtering by the foreign share id yields nothing
        data = self.client.get('/bioshare/api/logs/',
                               {'share': self.private_share.id}).json()
        self.assertEqual(data['count'], 0)

    def test_foreign_share_file_access_denied(self):
        self.login(self.viewer)  # has perms on self.share only
        response = self.client.get(reverse('download_file', kwargs={
            'share': self.private_share.id, 'subpath': 'secret.txt'}), **AJAX)
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(b'top secret', getattr(response, 'content', b''))

    def test_group_detail_hidden_from_non_member(self):
        self.login(self.other)
        response = self.client.get('/bioshare/api/groups/%d/' % self.group.id)
        self.assertEqual(response.status_code, 404)

    def test_group_update_users_requires_manage_group(self):
        self.login(self.group_user)  # member, but no manage_group permission
        payload = {'users': [{'id': self.other.id, 'permissions': []}]}
        response = self.client.post(
            '/bioshare/api/groups/%d/update_users/' % self.group.id,
            json.dumps(payload), content_type=JSON)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.other, self.group.user_set.all())

    def test_cannot_delete_other_users_ssh_key(self):
        key = SSHKey.objects.create(user=self.owner, name='k',
                                    key='ssh-rsa %s c' % ('A' * 372))
        self.login(self.other)
        response = self.client.post(reverse('api_delete_ssh_key'), {'id': key.id})
        self.assertEqual(self.json_of(response)['status'], 'error')
        self.assertTrue(SSHKey.objects.filter(id=key.id).exists())


class TestSymlinkEscapeOverHttp(ShareTestBase):
    """A symlink placed inside a share must not leak files outside the
    whitelist through the download endpoint."""

    def test_download_through_escaping_symlink_is_blocked(self):
        secret = os.path.join(self.outside_dir, 'secret.txt')
        with open(secret, 'w') as f:
            f.write('outside secret')
        os.symlink(secret, os.path.join(self.share.get_path(), 'leak.txt'))
        self.login(self.downloader)
        response = self.client.get(reverse('download_file', kwargs={
            'share': self.share.id, 'subpath': 'leak.txt'}), **AJAX)
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(b'outside secret', getattr(response, 'content', b''))


class TestCsrfProtection(ShareTestBase):
    """State-changing endpoints reject session-authenticated requests that
    lack a CSRF token (both plain Django views and DRF session auth)."""

    def test_plain_view_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.writer)
        url = reverse('create_folder', kwargs={'share': self.share.id})
        response = csrf_client.post(url, {'name': 'csrfless'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(os.path.exists(os.path.join(self.share.get_path(), 'csrfless')))

    def test_drf_view_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        url = reverse('api_update_share', kwargs={'share': self.share.id})
        response = csrf_client.post(url, json.dumps({'json': {'secure': False}}),
                                    content_type=JSON)
        self.assertEqual(response.status_code, 403)
        self.share.refresh_from_db()
        self.assertTrue(self.share.secure)


class TestRateLimiting(ShareTestBase):
    """The rate limiter is wired to the middleware and returns 429s."""

    RATES = {'default': '100/h', 'user': '100/h', 'anon': '100/h',
             'groups': {'search_share': {'user': '2/h', 'anon': '1/h'}}}

    def test_search_share_is_rate_limited(self):
        self.login(self.viewer)
        url = reverse('api_search_share', kwargs={'share': self.share.id})
        with override_settings(RATELIMIT_ENABLE=True, RATELIMIT_RATES=self.RATES):
            for i in range(2):
                response = self.client.get(url, {'query': 'hello'}, **AJAX)
                self.assertEqual(response.status_code, 200, 'request %d throttled early' % i)
            response = self.client.get(url, {'query': 'hello'}, **AJAX)
        self.assertEqual(response.status_code, 429)

    def test_exempt_username_is_not_rate_limited(self):
        self.login(self.viewer)
        url = reverse('api_search_share', kwargs={'share': self.share.id})
        with override_settings(RATELIMIT_ENABLE=True, RATELIMIT_RATES=self.RATES,
                               RATELIMIT_EXEMPT_USERNAMES=[self.viewer.username]):
            for _ in range(4):
                response = self.client.get(url, {'query': 'hello'}, **AJAX)
                self.assertEqual(response.status_code, 200)
