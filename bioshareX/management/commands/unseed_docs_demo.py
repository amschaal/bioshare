"""Remove everything `seed_docs_demo` created.

    python manage.py unseed_docs_demo --yes

Only objects named in `_docs_demo.py` are touched. Shares are matched on their
demo slug, accounts and groups on their exact names, so a real share or a real
account can never be caught by this even if it looks similar.

Deleting a Share removes its directory too -- `share_post_delete` calls
shutil.rmtree on the share path -- so the files seeded on disk go with it.
"""

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bioshareX.models import (EmailFooter, GroupProfile, Share, SSHKey,
                              UserProfile)

from . import _docs_demo as demo


class Command(BaseCommand):
    help = 'Delete the documentation demo data created by seed_docs_demo (DEBUG only).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Skip the confirmation prompt.',
        )
        parser.add_argument(
            '--user', default='test@fake.com',
            help='The account seed_docs_demo was run for. Its demo SSH key is '
                 'removed; the account itself is never deleted. '
                 'Default: test@fake.com',
        )
        parser.add_argument(
            '--prune-orphans', action='store_true',
            help='Also delete directories under the configured filesystems that '
                 'have no Share row pointing at them. Use this to clean up after '
                 'a seed run that failed part-way: the directory is created by '
                 'share_post_save before the rest of the seeding happens, so an '
                 'aborted run can leave directories behind with no share.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'unseed_docs_demo refuses to run with DEBUG=False. It deletes '
                'shares and the files underneath them.'
            )

        shares = Share.objects.filter(slug__in=demo.all_demo_share_slugs())
        users = User.objects.filter(username__in=demo.all_demo_usernames())
        groups = Group.objects.filter(name__in=demo.all_demo_group_names())

        self.stdout.write('This will delete:')
        self.stdout.write(f'  {shares.count()} share(s), including their files on disk')
        self.stdout.write(f'  {users.count()} demo account(s)')
        self.stdout.write(f'  {groups.count()} group(s)')

        if not (shares or users or groups):
            self.stdout.write(self.style.SUCCESS('Nothing to remove.'))
            return

        if not options['yes']:
            answer = input("Type 'yes' to continue: ")
            if answer.strip().lower() != 'yes':
                raise CommandError('Cancelled.')

        with transaction.atomic():
            # Order matters. Share.owner is PROTECT, so shares must go before the
            # accounts that own them.
            for share in shares:
                name = share.name
                share.delete()
                self.stdout.write(f'  - share {name}')

            removed_keys = SSHKey.objects.filter(
                user__username=options['user'].lower(),
                name=demo.DEMO_SSH_KEY_NAME,
            ).delete()[0]
            if removed_keys:
                self.stdout.write(f'  - ssh key {demo.DEMO_SSH_KEY_NAME}')

            EmailFooter.objects.filter(group__in=groups).delete()
            # GroupProfile.group is PROTECT, so the profile has to go first.
            GroupProfile.objects.filter(group__in=groups).delete()
            for group in groups:
                self.stdout.write(f'  - group {group.name}')
            groups.delete()

            # UserProfile.created_by is RESTRICT; clear any references between
            # demo accounts before deleting them.
            UserProfile.objects.filter(created_by__in=users).update(created_by=None)
            for user in users:
                self.stdout.write(f'  - user {user.username}')
            users.delete()

        if options['prune_orphans']:
            self._prune_orphans()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Demo data removed.'))

    def _prune_orphans(self):
        """Delete filesystem directories with no Share row pointing at them.

        A share directory is named after the share id, so any immediate child of a
        filesystem path whose name is not a known share id is unreferenced. Only
        directories are considered, and only ones matching the 15-character id
        format that pkgen produces, so unrelated content sitting on the volume is
        never touched.
        """
        import os
        import re
        import shutil

        from bioshareX.models import Filesystem

        known = set(Share.objects.values_list('id', flat=True))
        id_format = re.compile(r'^[0-9a-z]{15}$')
        pruned = 0

        for filesystem in Filesystem.objects.all():
            root = filesystem.path
            if not os.path.isdir(root):
                continue
            for entry in sorted(os.listdir(root)):
                path = os.path.join(root, entry)
                if entry in known or not id_format.match(entry):
                    continue
                if os.path.islink(path) or not os.path.isdir(path):
                    continue
                shutil.rmtree(path)
                self.stdout.write(f'  - orphaned directory {path}')
                pruned += 1

        self.stdout.write(f'  {pruned} orphaned director{"y" if pruned == 1 else "ies"} pruned')
