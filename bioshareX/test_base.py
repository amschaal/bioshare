"""
Shared fixtures for the bioshareX backend test suite.

Provides ShareTestBase, a TestCase that builds a complete, isolated
environment for exercising HTTP endpoints:

  * a Filesystem rooted in a temporary directory (whitelisted for the
    duration of the test, restored afterwards)
  * a Share owned by ``self.owner`` containing ``hello.txt`` and
    ``docs/notes.txt``
  * a cast of users, one per permission level, so authorization
    boundaries can be tested pairwise:

      owner       - owns self.share (implicitly holds every permission)
      viewer      - view_share_files
      downloader  - view_share_files + download_share_files
      writer      - view_share_files + write_to_share
      deleter     - view_share_files + delete_share_files
      sharer      - admin (and nothing else)
      other       - authenticated, no permissions on the share
      superuser   - is_superuser
      group_user  - member of self.group, no share permissions

Rate limiting is disabled for every test derived from this class; tests
that exercise the rate limiter re-enable it locally with
override_settings.

Run the whole suite with:  python manage.py test bioshareX
"""

import json
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm

from bioshareX.models import Filesystem, Share

# Header kwargs that make bioshareX.utils.is_ajax() return True, so
# permission failures come back as JSON errors instead of redirects.
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
PASSWORD = 'test-password-123'


@override_settings(RATELIMIT_ENABLE=False)
class ShareTestBase(TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()  # rate limit + du caches persist across tests otherwise
        self.fs_dir = tempfile.mkdtemp()
        self.outside_dir = tempfile.mkdtemp()
        self._old_settings = {}
        for key, value in (
            ('DIRECTORY_WHITELIST', [self.fs_dir]),
            ('LINK_TO_DIRECTORIES', [self.fs_dir]),
            ('SENDFILE_ROOTS', [self.fs_dir]),
        ):
            self._old_settings[key] = getattr(settings, key, None)
            setattr(settings, key, value)

        # django-guardian resolves anonymous requests via a User row matching
        # ANONYMOUS_USER_NAME exactly (the lowercase_user signal exempts it).
        anon_name = getattr(settings, 'ANONYMOUS_USER_NAME', 'AnonymousUser')
        User.objects.get_or_create(username=anon_name, defaults={'is_active': False})

        self.owner = self.make_user('owner')
        self.viewer = self.make_user('viewer')
        self.downloader = self.make_user('downloader')
        self.writer = self.make_user('writer')
        self.deleter = self.make_user('deleter')
        self.sharer = self.make_user('sharer')
        self.other = self.make_user('other')
        self.superuser = self.make_user('superuser', is_superuser=True, is_staff=True)

        self.group = Group.objects.create(name='testgroup')
        self.group_user = self.make_user('groupuser')
        self.group.user_set.add(self.group_user)

        self.filesystem = Filesystem.objects.create(
            name='testfs', description='test filesystem', path=self.fs_dir,
            type=Filesystem.TYPE_STANDARD)
        self.filesystem.users.add(self.owner, self.other, self.superuser)

        self.share = Share.objects.create(
            name='Main Share', notes='primary test share',
            owner=self.owner, filesystem=self.filesystem)
        self.write_share_file('hello.txt', b'Hello bioshare!\n')
        os.makedirs(os.path.join(self.share.get_path(), 'docs'))
        self.write_share_file(os.path.join('docs', 'notes.txt'), b'notes here\n')

        self.grant(self.viewer, Share.PERMISSION_VIEW)
        self.grant(self.downloader, Share.PERMISSION_VIEW, Share.PERMISSION_DOWNLOAD)
        self.grant(self.writer, Share.PERMISSION_VIEW, Share.PERMISSION_WRITE)
        self.grant(self.deleter, Share.PERMISSION_VIEW, Share.PERMISSION_DELETE)
        self.grant(self.sharer, Share.PERMISSION_ADMIN)

    def tearDown(self):
        for key, value in self._old_settings.items():
            setattr(settings, key, value)
        shutil.rmtree(self.fs_dir, ignore_errors=True)
        shutil.rmtree(self.outside_dir, ignore_errors=True)
        cache.clear()
        super().tearDown()

    # -- helpers -------------------------------------------------------------

    def make_user(self, name, **kwargs):
        return User.objects.create_user(
            username='%s@example.com' % name, email='%s@example.com' % name,
            password=PASSWORD, **kwargs)

    def grant(self, user_or_group, *perms, share=None):
        for perm in perms:
            assign_perm(perm, user_or_group, share or self.share)

    def give_global_perm(self, user, codename, app_label='bioshareX'):
        perm = Permission.objects.get(codename=codename,
                                      content_type__app_label=app_label)
        user.user_permissions.add(perm)

    def login(self, user):
        self.client.force_login(user)

    def make_share(self, owner, name='Second Share', **kwargs):
        return Share.objects.create(name=name, owner=owner,
                                    filesystem=self.filesystem, **kwargs)

    def write_share_file(self, subpath, content=b'data\n', share=None):
        share = share or self.share
        path = os.path.join(share.get_path(), subpath)
        with open(path, 'wb') as f:
            f.write(content)
        return path

    def json_of(self, response):
        return json.loads(response.content)
