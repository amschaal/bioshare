"""Create the demo dataset used for the user-guide screenshots.

    python manage.py seed_docs_demo

Everything it creates is listed in `_docs_demo.py`, and `unseed_docs_demo`
removes exactly that. Re-running is safe: existing objects are reused rather than
duplicated, so it can be used to top up a partially-seeded database.

Development only -- it refuses to run unless DEBUG is on, because it creates user
accounts with known-unusable passwords and grants them access to real shares.
"""

import os
import random

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from guardian.shortcuts import assign_perm

from bioshareX.models import (EmailFooter, Filesystem, GroupProfile, MetaData,
                              Share, ShareLog, SSHKey, Tag)

from . import _docs_demo as demo


class Command(BaseCommand):
    help = 'Create realistic demo data for documentation screenshots (DEBUG only).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            default='test@fake.com',
            help='Existing account the screenshots are taken with. It owns some '
                 'demo shares and is granted access to the others, so that both '
                 '"My latest shares" and "Recently shared with me" are populated. '
                 'Default: test@fake.com',
        )
        parser.add_argument(
            '--filesystem',
            default=None,
            help='Name of the Filesystem to create shares on. Defaults to the '
                 'first one configured.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'seed_docs_demo refuses to run with DEBUG=False. It creates '
                'accounts and grants share access, and is meant for a disposable '
                'development database only.'
            )

        try:
            docs_user = User.objects.get(username=options['user'].lower())
        except User.DoesNotExist:
            raise CommandError(
                f"No account '{options['user']}'. Pass --user with an existing "
                'account (the one you take screenshots with).'
            )

        if options['filesystem']:
            filesystem = Filesystem.objects.filter(name=options['filesystem']).first()
            if not filesystem:
                raise CommandError(f"No Filesystem named '{options['filesystem']}'.")
        else:
            filesystem = Filesystem.objects.first()
            if not filesystem:
                raise CommandError(
                    'No Filesystem is configured. Add one in the Django admin '
                    'first -- see the "Filesystem" section of the README.'
                )

        with transaction.atomic():
            users = self._create_users()
            users['docs'] = docs_user
            groups = self._create_groups(users, docs_user)
            self._create_email_footers(groups)
            shares = self._create_shares(users, groups, filesystem, docs_user)
            self._create_logs(shares, users, docs_user)
            self._create_ssh_key(docs_user)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready. Log in as {docs_user.username} to see it.'
        ))
        self.stdout.write('Remove it again with: python manage.py unseed_docs_demo')

    # -- accounts ------------------------------------------------------------
    def _create_users(self):
        users = {}
        for username, first, last in demo.DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': username, 'first_name': first, 'last_name': last},
            )
            if created:
                # Unusable password: these accounts exist to appear in permission
                # lists and share metadata, never to be logged into.
                user.set_unusable_password()
                user.save()
            users[username] = user
            self.stdout.write(f'  {"+" if created else "="} user {username}')
        return users

    # -- groups --------------------------------------------------------------
    def _create_groups(self, users, docs_user):
        groups = {}
        for name, description, members in demo.DEMO_GROUPS:
            group, created = Group.objects.get_or_create(name=name)
            GroupProfile.objects.get_or_create(
                group=group,
                defaults={'created_by': docs_user, 'description': description},
            )
            for member in members:
                users[member].groups.add(group)
            groups[name] = group
            self.stdout.write(f'  {"+" if created else "="} group {name}')
        return groups

    def _create_email_footers(self, groups):
        for group_name, title, content, is_default in demo.DEMO_EMAIL_FOOTERS:
            _footer, created = EmailFooter.objects.get_or_create(
                group=groups[group_name],
                title=title,
                defaults={'content': content, 'is_default': is_default},
            )
            self.stdout.write(f'  {"+" if created else "="} email footer {title}')

    # -- shares --------------------------------------------------------------
    def _create_shares(self, users, groups, filesystem, docs_user):
        shares = {}
        for spec in demo.DEMO_SHARES:
            owner = docs_user if spec['owner'] == 'docs' else users[spec['owner']]

            share = Share.objects.filter(slug=spec['slug']).first()
            created = share is None
            if created:
                # Creating the Share provisions its directory: share_post_save
                # makes filesystem.path/<id> (and share_post_delete removes it
                # again, which is what makes teardown clean).
                share = Share.objects.create(
                    name=spec['name'],
                    slug=spec['slug'],
                    owner=owner,
                    notes=spec['notes'],
                    read_only=spec['read_only'],
                    filesystem=filesystem,
                    secure=True,
                )
                for tag_name in spec['tags']:
                    tag, _ = Tag.objects.get_or_create(name=tag_name)
                    share.tags.add(tag)

            self._write_files(share, spec['layout'])
            self._assign_permissions(share, spec, users, groups, docs_user)
            self._create_metadata(share, spec)

            shares[spec['slug']] = share
            self.stdout.write(
                f'  {"+" if created else "="} share {spec["name"]} ({share.id})'
            )
        return shares

    def _write_files(self, share, layout):
        """Materialise the layout on disk, skipping anything already present."""
        os.umask(settings.UMASK)
        root = share.get_path()
        # Deterministic filler so re-seeding produces identical bytes, and so
        # screenshots do not churn between runs.
        rng = random.Random(share.slug)
        alphabet = 'ACGT'

        for relpath, size_kb in layout:
            full = os.path.join(root, relpath)
            parent = os.path.dirname(full)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            if os.path.exists(full):
                continue

            basename = os.path.basename(relpath)
            if basename == 'README.md':
                body = self._readme_for(share)
            elif basename in demo.FILE_CONTENT:
                body = demo.FILE_CONTENT[basename]
            else:
                # Filler shaped like sequence data so a preview looks plausible.
                line = ''.join(rng.choice(alphabet) for _ in range(70))
                repeats = max(1, (size_kb * 1024) // (len(line) + 1))
                body = '\n'.join([line] * repeats) + '\n'

            with open(full, 'w') as handle:
                handle.write(body)

    def _readme_for(self, share):
        return (
            f'# {share.name}\n\n'
            f'{share.notes}\n\n'
            '## Layout\n\n'
            '| Folder | Contents |\n'
            '|---|---|\n'
            '| `raw_reads` / `fastq` / `reads` | Sequence data as delivered |\n'
            '| `alignments` / `assembly` | Processed output |\n'
            '| `qc_reports` / `reports` | Quality control |\n\n'
            'A `README.md` at the top of a share is rendered underneath the file\n'
            'list, which makes it a good place to explain how the data is\n'
            'organised.\n'
        )

    def _assign_permissions(self, share, spec, users, groups, docs_user):
        for username, perms in spec.get('user_perms', {}).items():
            target = docs_user if username == 'docs' else users[username]
            for perm in perms:
                assign_perm(getattr(Share, demo.PERMISSION_ALIASES[perm]),
                            target, share)
        for group_name, perms in spec.get('group_perms', {}).items():
            for perm in perms:
                assign_perm(getattr(Share, demo.PERMISSION_ALIASES[perm]),
                            groups[group_name], share)

    def _create_metadata(self, share, spec):
        for subpath, notes, tags in spec.get('metadata', []):
            meta, _created = MetaData.objects.get_or_create(
                share=share, subpath=subpath, defaults={'notes': notes},
            )
            for tag_name in tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                meta.tags.add(tag)

    # -- activity log --------------------------------------------------------
    def _create_logs(self, shares, users, docs_user):
        created = 0
        for slug, action_attr, text, paths in demo.DEMO_LOGS:
            share = shares.get(slug)
            if not share:
                continue
            action = getattr(ShareLog, action_attr)
            if ShareLog.objects.filter(share=share, action=action,
                                       text=text, paths=paths).exists():
                continue
            # share_updated=False: bumping the share's modified timestamp on every
            # seed would make the home page's Modified column churn between runs.
            ShareLog.create(share, action, user=docs_user, text=text,
                            paths=paths, share_updated=False)
            created += 1
        self.stdout.write(f'  + {created} activity log entries')

    # -- ssh key -------------------------------------------------------------
    def _create_ssh_key(self, docs_user):
        if SSHKey.objects.filter(user=docs_user, name=demo.DEMO_SSH_KEY_NAME).exists():
            self.stdout.write(f'  = ssh key {demo.DEMO_SSH_KEY_NAME}')
            return
        try:
            import paramiko
            key = paramiko.RSAKey.generate(2048)
            body = key.get_base64()
        except Exception:
            self.stdout.write(self.style.WARNING(
                '  ! could not generate an RSA key (paramiko unavailable); '
                'skipping the demo SSH key'
            ))
            return
        SSHKey.objects.create(
            user=docs_user,
            name=demo.DEMO_SSH_KEY_NAME,
            # Stored in authorized_keys format, which is what SSHKey.extract_key
            # expects. The private half is discarded here and never written.
            key=f'ssh-rsa {body} {docs_user.username}',
        )
        self.stdout.write(f'  + ssh key {demo.DEMO_SSH_KEY_NAME}')
