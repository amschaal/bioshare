"""
Functional tests for the bioshareX backend: every JSON/API endpoint and the
file-operation views are exercised end-to-end with an authorized user and
asserted to do what they claim (DB state, filesystem state, emails, response
shape).

Authorization boundaries and abuse cases live in test_api_security.py;
path/symlink traversal internals live in test_path_security.py.

Run with:  python manage.py test bioshareX.test_api
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from unittest import mock, skipUnless

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from guardian.shortcuts import get_perms

from bioshareX.models import (EmailFooter, MetaData, Message, Share,
                              ShareLog, SSHKey, Tag)
from bioshareX.test_base import AJAX, ShareTestBase


class TestUserDirectoryEndpoints(ShareTestBase):
    """get_user / get_address_book / get_tags / get_group / share_autocomplete"""

    def test_get_user_by_email(self):
        self.login(self.owner)
        response = self.client.get(reverse('api_get_user'), {'query': self.viewer.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.json_of(response)['user']['email'], self.viewer.email)

    def test_get_user_unknown_returns_404(self):
        self.login(self.owner)
        response = self.client.get(reverse('api_get_user'), {'query': 'nobody@example.com'})
        self.assertEqual(response.status_code, 404)

    def test_get_address_book_contains_shared_users(self):
        self.login(self.owner)
        response = self.client.get(reverse('api_get_address_book'))
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertIn(self.viewer.email, data['emails'])
        self.assertIn(self.group.name, data['groups'])

    def test_get_tags_matches_substring(self):
        Tag.objects.create(name='genomics')
        Tag.objects.create(name='proteomics')
        Tag.objects.create(name='unrelated')
        self.login(self.owner)
        response = self.client.get(reverse('api_tags'), {'tag': 'omics'})
        data = self.json_of(response)
        self.assertEqual(sorted(data['tags']), ['genomics', 'proteomics'])

    def test_get_group_by_name(self):
        self.login(self.owner)
        response = self.client.get(reverse('api_get_group'), {'query': self.group.name})
        self.assertEqual(self.json_of(response)['group']['name'], self.group.name)

    def test_share_autocomplete_returns_visible_shares(self):
        self.login(self.viewer)
        response = self.client.get(reverse('api_share_autocomplete'), {'query': 'Main'})
        data = self.json_of(response)
        self.assertEqual(data['status'], 'success')
        self.assertIn(self.share.id, [s['id'] for s in data['shares']])

    def test_share_autocomplete_excludes_unshared(self):
        self.login(self.other)
        response = self.client.get(reverse('api_share_autocomplete'), {'query': 'Main'})
        self.assertEqual(self.json_of(response)['shares'], [])


class TestPermissionEndpoints(ShareTestBase):
    """get_permissions / set_permissions / update_share / share_with / share_read_only"""

    def test_get_permissions_lists_user_perms(self):
        self.login(self.owner)
        url = reverse('api_get_permissions', kwargs={'share': self.share.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertIn(self.viewer.username, data['user_perms'])
        self.assertIn(Share.PERMISSION_VIEW,
                      data['user_perms'][self.viewer.username]['permissions'])

    def test_set_permissions_grants_perms_to_existing_user(self):
        self.login(self.owner)
        url = reverse('api_set_permissions', kwargs={'share': self.share.id})
        payload = {'json': {
            'users': {self.other.username: [Share.PERMISSION_VIEW, Share.PERMISSION_DOWNLOAD]},
            'email': False,
        }}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        perms = get_perms(self.other, self.share)
        self.assertIn(Share.PERMISSION_VIEW, perms)
        self.assertIn(Share.PERMISSION_DOWNLOAD, perms)
        self.assertEqual(len(mail.outbox), 0)

    def test_set_permissions_revokes_removed_perms(self):
        self.login(self.owner)
        url = reverse('api_set_permissions', kwargs={'share': self.share.id})
        payload = {'json': {'users': {self.viewer.username: []}, 'email': False}}
        self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(get_perms(self.viewer, self.share), [])

    def test_set_permissions_for_new_email_creates_account_and_emails(self):
        self.login(self.owner)
        url = reverse('api_set_permissions', kwargs={'share': self.share.id})
        payload = {'json': {'users': {'brandnew@example.com': [Share.PERMISSION_VIEW]},
                            'email': True}}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        new_user = User.objects.get(username='brandnew@example.com')
        self.assertIn(Share.PERMISSION_VIEW, get_perms(new_user, self.share))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('brandnew@example.com', mail.outbox[0].to)

    def test_set_permissions_group(self):
        self.login(self.owner)
        url = reverse('api_set_permissions', kwargs={'share': self.share.id})
        payload = {'json': {'groups': {str(self.group.id): [Share.PERMISSION_VIEW]},
                            'email': False}}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(Share.PERMISSION_VIEW, get_perms(self.group, self.share))

    def test_update_share_toggles_secure(self):
        self.login(self.owner)
        url = reverse('api_update_share', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({'json': {'secure': False}}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.share.refresh_from_db()
        self.assertFalse(self.share.secure)

    def test_share_with_classifies_query(self):
        self.login(self.owner)
        url = reverse('api_share_with', kwargs={'share': self.share.id})
        query = '%s, group:%s, newperson@example.com, not-an-email' % (
            self.viewer.email, self.group.name)
        response = self.client.get(url, {'query': query})
        data = self.json_of(response)
        self.assertEqual(data['exists'][0]['user']['username'], self.viewer.email)
        self.assertEqual(data['groups'][0]['group']['name'], self.group.name)
        self.assertEqual(data['new_users'][0]['user']['username'], 'newperson@example.com')
        self.assertEqual(data['invalid'], ['not-an-email'])

    def test_share_read_only_grants_view_and_download(self):
        self.login(self.owner)
        url = reverse('api_share_read_only', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({'email': 'readonly@example.com'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='readonly@example.com')
        perms = get_perms(user, self.share)
        self.assertIn(Share.PERMISSION_VIEW, perms)
        self.assertIn(Share.PERMISSION_DOWNLOAD, perms)
        self.assertNotIn(Share.PERMISSION_WRITE, perms)

    def test_share_read_only_invalid_email_is_400(self):
        self.login(self.owner)
        url = reverse('api_share_read_only', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({'email': 'not-an-email'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)


class TestShareCreationAndAdmin(ShareTestBase):
    """API + web share creation, edit, stats, delete."""

    def test_api_create_share(self):
        self.give_global_perm(self.owner, 'add_share')
        self.login(self.owner)
        response = self.client.post(reverse('api_create_share'), json.dumps({
            'name': 'API Created Share', 'notes': 'created via API',
            'filesystem': self.filesystem.id,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        data = self.json_of(response)
        share = Share.objects.get(id=data['id'])
        self.assertEqual(share.owner, self.owner)
        self.assertTrue(os.path.isdir(share.get_path()))

    def test_api_create_share_missing_name_is_400(self):
        self.give_global_perm(self.owner, 'add_share')
        self.login(self.owner)
        response = self.client.post(reverse('api_create_share'),
                                    json.dumps({'notes': 'no name'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', self.json_of(response)['errors'])

    def test_web_create_share(self):
        self.give_global_perm(self.owner, 'add_share')
        self.login(self.owner)
        response = self.client.post(reverse('create_share'), {
            'name': 'Web Created Share', 'notes': 'created via form',
            'filesystem': self.filesystem.id, 'tags': 'alpha, beta',
        })
        self.assertEqual(response.status_code, 302)
        share = Share.objects.get(name='Web Created Share')
        self.assertTrue(os.path.isdir(share.get_path()))
        self.assertEqual(sorted(t.name for t in share.tags.all()), ['alpha', 'beta'])

    def test_edit_share_updates_name(self):
        self.login(self.owner)
        url = reverse('edit_share', kwargs={'share': self.share.id})
        response = self.client.post(url, {
            'name': 'Renamed Share', 'notes': 'primary test share',
            'filesystem': self.filesystem.id, 'tags': '',
        })
        self.assertEqual(response.status_code, 302)
        self.share.refresh_from_db()
        self.assertEqual(self.share.name, 'Renamed Share')

    def test_delete_share_requires_confirm(self):
        self.login(self.owner)
        path = self.share.get_path()
        response = self.client.get(reverse('delete_share', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Share.objects.filter(id=self.share.id).exists())
        self.assertTrue(os.path.isdir(path))

    def test_confirm_delete_share_removes_share_and_files(self):
        self.login(self.owner)
        path = self.share.get_path()
        response = self.client.get(
            reverse('confirm_delete_share', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Share.objects.filter(id=self.share.id).exists())
        self.assertFalse(os.path.exists(path))

    def test_update_stats_redirects_to_listing(self):
        self.login(self.owner)
        response = self.client.get(reverse('update_stats', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 302)
        self.share.refresh_from_db()
        self.assertGreater(self.share.stats.bytes, 0)

    def test_nonexistent_share_returns_500_message_page(self):
        self.login(self.owner)
        response = self.client.get(
            reverse('list_directory', kwargs={'share': 'zzzzzzzzzzzzzzz'}))
        self.assertEqual(response.status_code, 500)


class TestFileEndpoints(ShareTestBase):
    """upload / folder / rename / delete / move / download / preview / listing"""

    def test_upload_file(self):
        self.login(self.writer)
        url = reverse('upload_file', kwargs={'share': self.share.id})
        f = io.BytesIO(b'uploaded content')
        f.name = 'upload me.txt'
        response = self.client.post(url, {'file': f})
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertEqual(data['errors'], [])
        # spaces are converted to underscores by clean_filename
        self.assertEqual(data['files'][0]['name'], 'upload_me.txt')
        with open(os.path.join(self.share.get_path(), 'upload_me.txt'), 'rb') as fh:
            self.assertEqual(fh.read(), b'uploaded content')

    def test_upload_file_to_subdir(self):
        self.login(self.writer)
        url = reverse('upload_file', kwargs={'share': self.share.id, 'subdir': 'docs/'})
        f = io.BytesIO(b'sub content')
        f.name = 'sub.txt'
        response = self.client.post(url, {'file': f})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'docs', 'sub.txt')))

    def test_create_folder(self):
        self.login(self.writer)
        url = reverse('create_folder', kwargs={'share': self.share.id})
        response = self.client.post(url, {'name': 'newfolder'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.json_of(response)['status'], 'success')
        self.assertTrue(os.path.isdir(os.path.join(self.share.get_path(), 'newfolder')))

    def test_create_folder_illegal_name_rejected(self):
        self.login(self.writer)
        url = reverse('create_folder', kwargs={'share': self.share.id})
        response = self.client.post(url, {'name': 'bad/name'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.share.get_path(), 'bad')))

    def test_rename_file(self):
        self.login(self.writer)
        url = reverse('modify_name', kwargs={'share': self.share.id})
        response = self.client.post(url, {'from_name': 'hello.txt', 'to_name': 'hi.txt'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.json_of(response)['status'], 'success')
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hi.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_rename_to_illegal_name_rejected(self):
        self.login(self.writer)
        url = reverse('modify_name', kwargs={'share': self.share.id})
        response = self.client.post(url, {'from_name': 'hello.txt', 'to_name': 'a/b.txt'})
        self.assertEqual(self.json_of(response)['status'], 'error')
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_delete_paths(self):
        self.login(self.deleter)
        url = reverse('delete_paths', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({'selection': ['hello.txt']}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.json_of(response)['deleted'], ['hello.txt'])
        self.assertFalse(os.path.exists(os.path.join(self.share.get_path(), 'hello.txt')))

    def test_delete_missing_path_reports_failed(self):
        self.login(self.deleter)
        url = reverse('delete_paths', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({'selection': ['nope.txt']}),
                                    content_type='application/json')
        self.assertEqual(self.json_of(response)['failed'], ['nope.txt'])

    def test_move_paths(self):
        self.login(self.deleter)
        url = reverse('move_paths', kwargs={'share': self.share.id})
        payload = {'json': {'selection': ['hello.txt'], 'destination': 'docs'}}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.json_of(response)['moved'], ['hello.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'docs', 'hello.txt')))

    def test_download_file_content(self):
        self.login(self.downloader)
        url = reverse('download_file', kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'Hello bioshare!\n')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('Content-Security-Policy', response)

    def test_download_updates_last_data_access(self):
        self.login(self.downloader)
        self.assertIsNone(self.share.last_data_access)
        url = reverse('download_file', kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        self.client.get(url)
        self.share.refresh_from_db()
        self.assertIsNotNone(self.share.last_data_access)

    def test_preview_file(self):
        self.login(self.downloader)
        url = reverse('preview_file', kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url, {'from': 1, 'for': 10, 'get_total': 1})
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertIn('Hello bioshare!', data['content'])
        self.assertEqual(data['total'], 1)

    def test_get_directories(self):
        self.login(self.downloader)
        url = reverse('get_directories', kwargs={'share': self.share.id})
        response = self.client.get(url, {'directory': ''})
        self.assertEqual(response.status_code, 200)
        self.assertIn('docs', [d['title'] for d in self.json_of(response)])

    @skipUnless(shutil.which('md5sum'), 'md5sum binary not available')
    def test_md5sum_matches_hashlib(self):
        self.login(self.viewer)
        url = reverse('md5sum', kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected = hashlib.md5(b'Hello bioshare!\n').hexdigest()
        self.assertEqual(self.json_of(response)['md5sum'], expected)

    def test_download_archive_stream_returns_zip(self):
        self.login(self.downloader)
        url = reverse('download_archive_stream', kwargs={'share': self.share.id})
        response = self.client.get(url, {'selection': 'hello.txt,docs'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content)))
        names = archive.namelist()
        self.assertIn('hello.txt', names)
        self.assertTrue(any(n.endswith('notes.txt') for n in names))

    def test_list_directory_ajax_json(self):
        self.login(self.viewer)
        url = reverse('list_directory', kwargs={'share': self.share.id})
        response = self.client.get(url, **AJAX)
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertIn('hello.txt', [f['name'] for f in data['files']])
        self.assertIn('docs', [d['name'] for d in data['directories']])

    def test_list_directory_html(self):
        self.login(self.viewer)
        response = self.client.get(reverse('list_directory', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hello.txt')

    def test_wget_listing(self):
        self.login(self.downloader)
        response = self.client.get(reverse('wget_listing', kwargs={'share': self.share.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hello.txt')

    def test_go_to_file_redirects_to_download(self):
        self.login(self.viewer)
        url = reverse('go_to_file_or_folder',
                      kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('download_file',
                              kwargs={'share': self.share.id, 'subpath': 'hello.txt'}),
                      response['Location'])

    def test_go_to_folder_redirects_to_listing(self):
        self.login(self.viewer)
        url = reverse('go_to_file_or_folder',
                      kwargs={'share': self.share.id, 'subpath': 'docs'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/docs/', response['Location'])


class TestSymlinkEndpoints(ShareTestBase):
    """create_symlink / unlink for users with the link_to_path permission."""

    def setUp(self):
        super().setUp()
        self._old_enable = settings.ENABLE_SYMLINKS
        settings.ENABLE_SYMLINKS = True
        from bioshareX.models import FilePath
        self.link_target = os.path.join(self.fs_dir, 'link_target')
        os.makedirs(self.link_target)
        self.filepath = FilePath.objects.create(path=self.fs_dir, regexes=[])
        self.filepath.users.add(self.owner)
        self.give_global_perm(self.owner, 'link_to_path')

    def tearDown(self):
        settings.ENABLE_SYMLINKS = self._old_enable
        super().tearDown()

    def test_create_symlink(self):
        self.login(self.owner)
        url = reverse('create_symlink', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({
            'name': 'mylink', 'target': self.link_target,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        link = os.path.join(self.share.get_path(), 'mylink')
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(self.link_target))

    def test_create_symlink_outside_whitelist_rejected(self):
        self.login(self.owner)
        url = reverse('create_symlink', kwargs={'share': self.share.id})
        response = self.client.post(url, json.dumps({
            'name': 'evil', 'target': self.outside_dir,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(os.path.lexists(os.path.join(self.share.get_path(), 'evil')))

    def test_unlink_removes_symlink(self):
        link = os.path.join(self.share.get_path(), 'gone')
        os.symlink(self.link_target, link)
        self.login(self.owner)
        url = reverse('unlink', kwargs={'share': self.share.id, 'subpath': 'gone'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(os.path.lexists(link))

    def test_unlink_non_symlink_errors(self):
        self.login(self.owner)
        url = reverse('unlink', kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(os.path.isfile(os.path.join(self.share.get_path(), 'hello.txt')))


class TestSearchAndMetadata(ShareTestBase):

    def test_search_finds_file(self):
        self.login(self.viewer)
        url = reverse('api_search_share', kwargs={'share': self.share.id})
        response = self.client.get(url, {'query': 'hello'})
        self.assertEqual(response.status_code, 200)
        results = self.json_of(response)['results']
        self.assertIn('/%s/hello.txt' % self.share.id, results)

    def test_search_without_query_errors(self):
        self.login(self.viewer)
        url = reverse('api_search_share', kwargs={'share': self.share.id})
        response = self.client.get(url)
        self.assertEqual(self.json_of(response)['status'], 'error')

    def test_edit_metadata_sets_tags_and_notes(self):
        self.login(self.writer)
        url = reverse('api_edit_metadata',
                      kwargs={'share': self.share.id, 'subpath': 'hello.txt'})
        response = self.client.post(url, {'notes': 'important file', 'tags': 'alpha, beta'})
        self.assertEqual(response.status_code, 200)
        data = self.json_of(response)
        self.assertEqual(data['notes'], 'important file')
        self.assertEqual(sorted(data['tags']), ['alpha', 'beta'])
        md = MetaData.objects.get(share=self.share, subpath='hello.txt')
        self.assertEqual(md.notes, 'important file')

    def test_edit_metadata_missing_path_errors(self):
        self.login(self.writer)
        url = reverse('api_edit_metadata',
                      kwargs={'share': self.share.id, 'subpath': 'missing.txt'})
        response = self.client.post(url, {'notes': 'x', 'tags': ''})
        self.assertEqual(response.status_code, 400)


class TestEmailEndpoints(ShareTestBase):

    def test_email_participants_sends_to_permitted_users_and_owner(self):
        self.login(self.viewer)
        url = reverse('api_email_participants',
                      kwargs={'share': self.share.id, 'subdir': ''})
        response = self.client.post(url, {'subject': 'Data ready',
                                          'body': 'The run finished.'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.owner.email, mail.outbox[0].to)
        self.assertIn(self.viewer.email, mail.outbox[0].to)
        self.assertEqual(mail.outbox[0].subject, 'Data ready')
        log = ShareLog.objects.filter(share=self.share,
                                      action=ShareLog.ACTION_USER_EMAILED)
        self.assertTrue(log.exists())

    def test_email_participants_filtered_recipients(self):
        self.login(self.owner)
        url = reverse('api_email_participants',
                      kwargs={'share': self.share.id, 'subdir': ''})
        response = self.client.post(url, {'subject': 's', 'body': 'b',
                                          'emails': [self.viewer.email]})
        self.assertEqual(response.status_code, 200)
        sent_to = self.json_of(response)['sent_to']
        self.assertIn(self.viewer.email, sent_to)
        self.assertNotIn(self.writer.email, sent_to)


class TestRestViewsets(ShareTestBase):
    """DRF router endpoints: shares, logs, groups, messages."""

    def test_shares_list_scoped_to_user(self):
        self.make_share(self.other, name='Not Mine')
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/')
        self.assertEqual(response.status_code, 200)
        ids = [s['id'] for s in response.json()['results']]
        self.assertEqual(ids, [self.share.id])

    def test_shares_detail(self):
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/%s/' % self.share.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Main Share')

    def test_shares_name_filter(self):
        self.login(self.owner)
        response = self.client.get('/bioshare/api/shares/', {'name__icontains': 'zzz-no-match'})
        self.assertEqual(response.json()['count'], 0)
        response = self.client.get('/bioshare/api/shares/', {'name__icontains': 'main'})
        self.assertEqual(response.json()['count'], 1)

    def test_shares_directory_size(self):
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/%s/directory_size/' % self.share.id)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['share'], self.share.id)
        self.assertTrue(data['size'])

    def test_shares_export_csv(self):
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/shares/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(self.share.id, response.content.decode())

    def test_logs_visible_for_permitted_share(self):
        ShareLog.create(share=self.share, user=self.owner,
                        action=ShareLog.ACTION_FILE_ADDED, paths=['hello.txt'])
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/logs/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()['count'], 1)

    def test_logs_filter_by_action(self):
        ShareLog.create(share=self.share, user=self.owner,
                        action=ShareLog.ACTION_FILE_ADDED, paths=['hello.txt'])
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/logs/', {'action__icontains': 'file added'})
        self.assertEqual(response.json()['count'], 1)
        response = self.client.get('/bioshare/api/logs/', {'action__icontains': 'renamed'})
        self.assertEqual(response.json()['count'], 0)

    def test_groups_list_scoped_to_membership(self):
        Group.objects.create(name='someone-elses-group')
        self.login(self.group_user)
        response = self.client.get('/bioshare/api/groups/')
        names = [g['name'] for g in response.json()['results']]
        self.assertEqual(names, [self.group.name])

    def test_groups_list_superuser_sees_all(self):
        Group.objects.create(name='someone-elses-group')
        self.login(self.superuser)
        response = self.client.get('/bioshare/api/groups/')
        names = [g['name'] for g in response.json()['results']]
        self.assertIn('someone-elses-group', names)

    def test_group_update_users(self):
        manager = self.group_user
        from guardian.shortcuts import assign_perm
        assign_perm('manage_group', manager, self.group)
        self.login(manager)
        payload = {'users': [
            {'id': manager.id, 'permissions': ['manage_group']},
            {'id': self.other.id, 'permissions': []},
        ]}
        response = self.client.post('/bioshare/api/groups/%d/update_users/' % self.group.id,
                                    json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        members = set(self.group.user_set.values_list('id', flat=True))
        self.assertEqual(members, {manager.id, self.other.id})

    def test_messages_list_and_dismiss(self):
        message = Message.objects.create(title='Maintenance tonight')
        self.login(self.viewer)
        response = self.client.get('/bioshare/api/messages/', {'active': 'true'})
        self.assertIn(message.id, [m['id'] for m in response.json()['results']])
        response = self.client.post('/bioshare/api/messages/%d/dismiss/' % message.id)
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/bioshare/api/messages/', {'active': 'true'})
        self.assertNotIn(message.id, [m['id'] for m in response.json()['results']])


class TestSSHKeys(ShareTestBase):

    FAKE_KEY = 'ssh-rsa %s comment' % ('A' * 372)

    def test_create_authorized_key_line_format(self):
        key = SSHKey.objects.create(user=self.owner, name='k', key=self.FAKE_KEY)
        line = key.create_authorized_key()
        self.assertIn('command="', line)
        self.assertIn('rsync %s' % self.owner.username, line)
        self.assertIn('A' * 372, line)

    def test_create_authorized_key_rejects_illegal_username(self):
        evil = User(username='evil"user', email='x@example.com')
        key = SSHKey(user=evil, name='k', key=self.FAKE_KEY)
        with self.assertRaises(Exception):
            key.create_authorized_key()

    def test_delete_ssh_key_removes_db_row_and_authorized_keys_line(self):
        key = SSHKey.objects.create(user=self.owner, name='mine', key=self.FAKE_KEY)
        fd, keys_file = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as f:
                f.write('command="x" ssh-rsa %s %s\n' % ('A' * 372, self.owner.username))
                f.write('command="x" ssh-rsa %s other\n' % ('B' * 372))
            self.login(self.owner)
            with mock.patch('bioshareX.api.views.AUTHORIZED_KEYS_FILE', keys_file):
                response = self.client.post(reverse('api_delete_ssh_key'), {'id': key.id})
            self.assertEqual(self.json_of(response)['status'], 'success')
            self.assertFalse(SSHKey.objects.filter(id=key.id).exists())
            with open(keys_file) as f:
                remaining = f.read()
            self.assertNotIn('A' * 372, remaining)
            self.assertIn('B' * 372, remaining)  # other keys untouched
        finally:
            os.unlink(keys_file)

    @skipUnless(shutil.which('ssh-keygen'), 'ssh-keygen not available')
    @override_settings(FILE_UPLOAD_HANDLERS=[
        'django.core.files.uploadhandler.TemporaryFileUploadHandler'])
    def test_create_ssh_key_via_view(self):
        keydir = tempfile.mkdtemp()
        try:
            keypath = os.path.join(keydir, 'id_rsa')
            subprocess.check_call(['ssh-keygen', '-q', '-t', 'rsa', '-b', '3072',
                                   '-N', '', '-f', keypath])
            keys_file = os.path.join(keydir, 'authorized_keys')
            open(keys_file, 'w').close()
            self.login(self.owner)
            with mock.patch('settings.settings.AUTHORIZED_KEYS_FILE', keys_file):
                with open(keypath + '.pub', 'rb') as pub:
                    response = self.client.post(reverse('create_ssh_key'),
                                                {'name': 'laptop', 'rsa_key': pub})
            self.assertEqual(response.status_code, 302)
            key = SSHKey.objects.get(user=self.owner, name='laptop')
            with open(keys_file) as f:
                self.assertIn(key.get_key(), f.read())
        finally:
            shutil.rmtree(keydir, ignore_errors=True)


class TestEmailFooters(ShareTestBase):
    """Per-group customizable email footers (EmailFooter model + ShareForm)."""

    def setUp(self):
        super().setUp()
        self.footer = EmailFooter.objects.create(
            title='Lab footer', content='<p>The Lab</p>', group=self.group)

    def test_share_uses_selected_footer(self):
        self.share.email_footer = self.footer
        self.share.save()
        self.assertEqual(self.share.get_email_footer_html(), '<p>The Lab</p>')

    def test_share_without_footer_falls_back_to_default_template(self):
        html = self.share.get_email_footer_html()
        self.assertIsInstance(html, str)
        self.assertNotEqual(html.strip(), '')
        self.assertNotIn('The Lab', html)

    def test_share_notification_email_includes_footer(self):
        self.share.email_footer = self.footer
        self.share.save()
        self.login(self.owner)
        url = reverse('api_set_permissions', kwargs={'share': self.share.id})
        payload = {'json': {'users': {self.other.username: [Share.PERMISSION_VIEW]},
                            'email': True}}
        self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('The Lab', mail.outbox[0].body)

    def test_form_offers_footers_of_own_group_only(self):
        from bioshareX.forms import ShareForm
        other_group = Group.objects.create(name='othergroup')
        other_footer = EmailFooter.objects.create(
            title='Other footer', content='x', group=other_group)
        form = ShareForm(self.group_user)
        qs = form.fields['email_footer'].queryset
        self.assertIn(self.footer, qs)
        self.assertNotIn(other_footer, qs)
        form = ShareForm(self.superuser)
        self.assertIn(other_footer, form.fields['email_footer'].queryset)

    def test_form_hides_footer_field_when_none_available(self):
        from bioshareX.forms import ShareForm
        form = ShareForm(self.other)  # not in any group
        self.assertNotIn('email_footer', form.fields)

    def test_form_keeps_out_of_group_selection_on_edit(self):
        from bioshareX.forms import ShareForm
        other_group = Group.objects.create(name='othergroup')
        other_footer = EmailFooter.objects.create(
            title='Other footer', content='x', group=other_group)
        self.share.email_footer = other_footer
        self.share.save()
        self.group.user_set.add(self.owner)
        form = ShareForm(self.owner, instance=self.share)
        self.assertIn(other_footer, form.fields['email_footer'].queryset)

    def test_default_footer_preselected_for_group_member(self):
        from bioshareX.forms import ShareForm
        self.footer.is_default = True
        self.footer.save()
        form = ShareForm(self.group_user)
        self.assertEqual(form.initial.get('email_footer'), self.footer)
