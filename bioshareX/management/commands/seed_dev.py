"""
Seed a development database with users, groups and shares, and build each
share's directory on disk to match.

    python manage.py seed_dev                    # create the seed, or restore it
    python manage.py seed_dev --reset            # delete everything it made first
    python manage.py seed_dev --path /data/bioshare/dev-seed --password 'pw'

Run it where the web app runs (the dev web container): share directories are
written to that machine's disk. They go under --path, which defaults to a
"dev-seed" folder in the first FILESYSTEM_DIRECTORIES entry and has to be
inside DIRECTORY_WHITELIST, because the app refuses to list shares outside it.
Refuses to run unless DEBUG is on, since every account it makes shares one
known password. It never sends email.

What the seed covers:

  users       a superuser; an is_staff user who can create groups; users with
              and without add_share and link_to_path; two filesystems for one
              user; an external collaborator auto-created by a share (no name,
              never logged in, profile.created_by set); a deactivated account;
              a brand-new account with nothing
  groups      managers and members (manage_group), an empty group, a member
              who only sees shares through a group, default and alternate
              email footers
  shares      per-user and per-group permissions at every level, read-only,
              public (secure=False), locked by an illegal symlink, a missing
              directory, a subshare, a linked share (when LINK_TO_DIRECTORIES
              is set), a legal internal symlink, slugs, tags, file metadata,
              activity logs, an empty share, a 288-file share, README.md
              rendering, unicode and spaced filenames, a 20 MB file
  messages    active, expiring, expired, inactive, dismissed by some users

Re-running restores the seed's users (passwords included), groups, permissions
and share settings to what is defined below, but never overwrites or deletes files: anything you have
since uploaded stays. Use --reset for a clean slate. All file content is
synthetic: random sequence with plausible names and formats.

The data is the module-level USERS, FILESYSTEMS, GROUPS, EMAIL_FOOTERS, SHARES
and MESSAGES below; the LAYOUTS builders write each share's files.
"""
import gzip
import hashlib
import io
import math
import os
import re
import random
import shutil
import struct
import tempfile
import zlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q, RestrictedError
from django.db.models.signals import post_delete
from django.utils import timezone
from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm, remove_perm

from bioshareX.forms import ShareForm
from bioshareX.models import (EmailFooter, FilePath, Filesystem, GroupProfile,
                              Message, MetaData, Share,
                              ShareGroupObjectPermission, ShareLog,
                              ShareUserObjectPermission, Tag, UserProfile,
                              share_post_delete)
from bioshareX.utils import paths_contain

DEFAULT_PASSWORD = 'bioshare-dev-password'

# Where the locked share's symlink may point: the first of these parents that
# is writable and leaves the link outside DIRECTORY_WHITELIST (some dev
# configs whitelist /tmp).
OUTSIDE_NAME = 'bioshare-dev-seed-outside'
OUTSIDE_PARENTS = (tempfile.gettempdir(), '/var/tmp', os.path.expanduser('~'))
# Created inside LINK_TO_DIRECTORIES[0] to hold the linked share's target.
LINK_DIR_NAME = 'bioshare-dev-seed-instruments'
FILEPATH_NAME = 'Dev seed: sequencer output'
# The first is linked as a share; the second is left for linking by hand.
LINKED_RUNS = ['261102_A00123_0456_BHXXXXDSX5', '261109_A00123_0461_AHYYYYDSX5']

VIEW = 'view_share_files'
DOWNLOAD = 'download_share_files'
WRITE = 'write_to_share'
DELETE = 'delete_share_files'
ADMIN = 'admin'
SHARE_READ_ONLY = 'share_read_only'
FULL = [VIEW, DOWNLOAD, WRITE, DELETE, ADMIN]


# --- the data ---------------------------------------------------------------
# joined / last_login / created / updated / accessed are days before now.

USERS = {
    'admin': dict(email='site.admin@example.com', first_name='Site', last_name='Admin',
                  is_superuser=True, is_staff=True, joined=900, last_login=0,
                  role='Superuser. Sees every share; can unlock the locked one.'),
    'maria': dict(email='maria.lopez@example.com', first_name='Maria', last_name='Lopez',
                  is_staff=True, perms=['add_share', 'link_to_path'], joined=800, last_login=1,
                  role='Core staff (is_staff): can create groups. Owns the linked share.'),
    'bob': dict(email='bob.patel@example.com', first_name='Bob', last_name='Patel',
                perms=['add_share'], joined=700, last_login=2,
                role='Core bioinformatician. Two filesystems, so the share form asks which.'),
    'alice': dict(email='alice.chen@example.com', first_name='Alice', last_name='Chen',
                  perms=['add_share'], joined=600, last_login=3,
                  role='Chen Lab PI. Manages Chen Lab and Plant Pathology Consortium.'),
    'carol': dict(email='carol.nguyen@example.com', first_name='Carol', last_name='Nguyen',
                  perms=['add_share'], joined=400, last_login=5,
                  role='Chen Lab postdoc, co-manager. Owns the locked share.'),
    'dan': dict(email='dan.okafor@example.com', first_name='Dan', last_name='Okafor',
                joined=200, last_login=10,
                role='Grad student. Cannot create shares; uploads to others\' shares.'),
    'erin': dict(email='erin.walsh@example.com', joined=45, last_login=None, created_by='alice',
                 role='External collaborator auto-created by a share: no name, never logged in.'),
    'farid': dict(email='farid.haddad@example.com', first_name='Farid', last_name='Haddad',
                  joined=300, last_login=20,
                  role='Consortium member. Sees shares only through the group.'),
    'grace': dict(email='grace.kim@example.com', first_name='Grace', last_name='Kim',
                  is_active=False, joined=1000, last_login=400,
                  role='Former lab member. Deactivated, still on share permissions.'),
    'henry': dict(email='henry.zhao@example.com', first_name='Henry', last_name='Zhao',
                  joined=2, last_login=1,
                  role='Brand-new account: no shares, no groups.'),
}

FILESYSTEMS = {
    'primary': dict(name='Dev seed: primary', subdir='primary',
                    users=['admin', 'maria', 'bob', 'alice', 'carol'],
                    description='Primary storage for seeded development shares.'),
    'archive': dict(name='Dev seed: archive', subdir='archive', users=['maria', 'bob'],
                    description='Archive tier for seeded development shares.'),
}

GROUPS = [
    dict(name='Genomics Core', created_by='maria', members=['maria', 'bob'], managers=['maria'],
         description='Sequencing and bioinformatics core. Delivers data to labs.'),
    dict(name='Chen Lab', created_by='maria', members=['alice', 'carol', 'dan', 'grace'],
         managers=['alice', 'carol'],
         description='Plant stress genomics. Alice Chen, PI.'),
    dict(name='Plant Pathology Consortium', created_by='maria', members=['alice', 'erin', 'farid'],
         managers=['alice'],
         description='Multi-site Fusarium isolate sequencing collaboration.'),
    dict(name='Proteomics Core', created_by='admin', members=[], managers=[],
         description='Set up ahead of onboarding; no members yet.'),
]

EMAIL_FOOTERS = [
    dict(group='Genomics Core', title='Genomics Core standard', is_default=True,
         content='<p>Questions about this data? Reply to this email or write to '
                 '<a href="mailto:genomics-core@example.com">genomics-core@example.com</a>.</p>'),
    dict(group='Genomics Core', title='Genomics Core billing reminder', is_default=False,
         content='<p>This delivery completes your order. Data is kept for 90 days; '
                 'please download it and confirm the checksums.</p>'),
    dict(group='Chen Lab', title='Chen Lab', is_default=True,
         content='<p>Chen Lab, Plant Stress Genomics. Please do not forward outside the lab.</p>'),
]

SHARES = [
    dict(id='seedchenrnaseq1', name='Chen Lab RNA-seq: heat stress time course',
         slug='chen-rnaseq-heat-stress', owner='bob', layout='rnaseq',
         notes='Paired-end 150 bp RNA-seq of 6 samples (3 control, 3 heat stress). '
               'Delivered by the Genomics Core.',
         tags=['rnaseq', 'illumina', 'chen_lab'], footer=('Genomics Core', 'Genomics Core standard'),
         users={'alice': FULL, 'carol': [VIEW, DOWNLOAD, WRITE], 'dan': [VIEW, DOWNLOAD],
                'grace': [VIEW, DOWNLOAD]},
         groups={'Chen Lab': [VIEW, DOWNLOAD]},
         created=75, updated=2, accessed=1,
         metadata=[('raw_data', 'Delivered by the core. Verify against md5sums.txt before '
                                'deleting local copies.', ['raw', 'delivered']),
                   ('results/counts/gene_counts.tsv', 'featureCounts against the demo '
                                                      'annotation, unstranded.', ['final'])],
         logs=[(75, 'bob', 'Folder Created', '', ['raw_data']),
               (75, 'bob', 'Files rsynced', 'rsync upload of 14 files', ['raw_data/fastq/']),
               (74, 'bob', 'Permissions updated', 'Shared with alice.chen@example.com and Chen Lab', []),
               (60, 'carol', 'File Added', '', ['analysis/qc/multiqc_report.html']),
               (44, 'carol', 'File/Folder Renamed', 'counts.txt to gene_counts.tsv',
                ['results/counts/gene_counts.tsv']),
               (30, 'alice', 'File(s)/Folder(s) Moved', '', ['docs/meeting notes (final v2).txt']),
               (9, 'carol', 'File(s)/Folder(s) Deleted', '', ['scratch/tmp_alignments.bam']),
               (2, 'alice', 'User emailed', 'An email has been sent to the following participants: '
                                            'carol.nguyen@example.com, dan.okafor@example.com', [])]),
    dict(id='seedchendeseq01', name='Heat stress RNA-seq: differential_expression',
         parent='seedchenrnaseq1', sub_directory='results/differential_expression/', owner='alice',
         notes="Shared from 'Chen Lab RNA-seq: heat stress time course': "
               "results/differential_expression/",
         users={'erin': [VIEW, DOWNLOAD]}, created=20, updated=20),
    dict(id='seedcorewgs0001', name='Core WGS pipeline validation', slug='core-wgs-validation',
         owner='maria', layout='wgs', tags=['wgs', 'validation', 'giab'],
         notes='GIAB trio on chr20, used to validate pipeline releases. Placeholder BAMs.',
         footer=('Genomics Core', 'Genomics Core billing reminder'),
         users={'bob': [ADMIN]}, groups={'Genomics Core': [VIEW, DOWNLOAD, WRITE, DELETE]},
         created=120, updated=9, accessed=9,
         logs=[(120, 'maria', 'Folder Created', '', ['bam']),
               (118, 'bob', 'File Added', '', ['vcf/trio.chr20.vcf.gz']),
               (9, 'bob', 'File Added', '', ['pipeline/logs/run_2026-07-18.log'])]),
    dict(id='seedarchive2019', name='2019 Methylation Project, archived', owner='bob',
         filesystem='archive', read_only=True, layout='methylation', tags=['archived', 'methylation'],
         notes='Read-only archive. Write and delete grants below are suppressed by read-only.',
         users={'alice': FULL}, groups={'Chen Lab': [VIEW, DOWNLOAD, WRITE]},
         created=700, updated=650, accessed=200),
    dict(id='seedpublicrefs1', name='Public reference genomes', slug='reference-genomes',
         owner='maria', secure=False, layout='reference', tags=['reference', 'public'],
         notes='Not secure: anyone with the link can view and download, no login needed.',
         users={'bob': [VIEW, DOWNLOAD, WRITE]}, created=365, updated=30, accessed=0),
    dict(id='seedplatereads1', name='Amplicon plate reads, 3 plates', owner='carol',
         layout='plates', tags=['amplicon', 'plates'],
         notes='3 plates x 96 wells, one small FASTQ per well: 288 files for paging and search.',
         users={'dan': [VIEW, DOWNLOAD, WRITE]}, groups={'Plant Pathology Consortium': [VIEW]},
         created=40, updated=5, accessed=5),
    dict(id='seedplantpath01', name='Plant Pathology Consortium: isolate assemblies',
         slug='plant-pathology-isolates', owner='alice', layout='consortium',
         tags=['assembly', 'fusarium', 'consortium'],
         notes='Draft assemblies from all sites. latest/ is a symlink to assemblies/v2/.',
         users={'erin': [VIEW, DOWNLOAD, WRITE, SHARE_READ_ONLY]},
         groups={'Plant Pathology Consortium': [VIEW, DOWNLOAD, WRITE]},
         created=150, updated=12, accessed=3,
         metadata=[('assemblies/v1', 'Superseded. Kept for the methods comparison.', ['superseded'])],
         logs=[(150, 'alice', 'Folder Created', '', ['assemblies']),
               (100, 'erin', 'File Added', '', ['assemblies/v1/Fo_OR_2023_007.contigs.fasta']),
               (12, 'farid', 'File Added', '', ['assemblies/v2/Fo_AZ_2022_011.contigs.fasta'])]),
    dict(id='seedmissingpath', name='Field trial images, moved', owner='alice', missing=True,
         notes='The directory was moved on disk, so the share shows an error.',
         users={'farid': [VIEW, DOWNLOAD]}, groups={'Plant Pathology Consortium': [VIEW, DOWNLOAD]},
         created=300, updated=290),
    dict(id='seedlockedshare', name="Carol's scratch space", owner='carol', layout='scratch',
         expect_locked=True,
         notes='Locked: shared_drive/ is a symlink outside the whitelist.',
         users={'dan': [VIEW, DOWNLOAD]}, created=30, updated=4),
    dict(id='seedemptyshare1', name='Incoming: Okafor thesis data', owner='carol',
         notes='Upload target, intentionally empty.',
         users={'dan': [VIEW, DOWNLOAD, WRITE, DELETE]}, created=1, updated=1),
    dict(id='seedlinkedrun01', name='NovaSeq run ' + LINKED_RUNS[0], owner='maria', linked=True,
         tags=['novaseq', 'run'],
         notes='Linked share: points at the run folder in LINK_TO_DIRECTORIES.',
         groups={'Genomics Core': [VIEW, DOWNLOAD]}, created=23, updated=23, accessed=20),
]

MESSAGES = [
    dict(title='Scheduled maintenance this weekend', active=True, created=3, expires_in=14,
         description='Bioshare will be unavailable Saturday 06:00 to 10:00 while storage is '
                     'upgraded. Transfers in progress will be interrupted.'),
    dict(title='New SFTP endpoint available', active=True, created=20, viewed_by=['maria', 'bob'],
         description='Connect with any SFTP client using your Bioshare login or an uploaded '
                     'SSH key.'),
    dict(title='Storage outage resolved', active=True, created=40, expires_in=-30,
         description='The archive filesystem is back. This message has expired and should not show.'),
    dict(title='Draft: holiday support hours', active=False, created=1,
         description='Inactive draft. This message should not show.'),
]


# --- file content -----------------------------------------------------------

def gz(data):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as f:
        f.write(data.encode() if isinstance(data, str) else data)
    return out.getvalue()


def random_seq(rng, length):
    return ''.join(rng.choices('ACGT', k=length))


def fastq_pair(rng, pairs, read_len=150, index='ACGTACGT+TTGCAGCA', flowcell='HXXXXDSX5'):
    # Mostly Q37 with a few Q25/Q11, like NovaSeq's binned scores.
    quals = 'F' * 18 + ':,'
    reads = ([], [])
    for i in range(pairs):
        name = '@A00123:456:%s:1:%d:%d:%d' % (flowcell, 1101 + i // 2000,
                                             rng.randrange(1000, 32000), rng.randrange(1000, 37000))
        for mate, lines in enumerate(reads, start=1):
            lines.append('%s %d:N:0:%s\n%s\n+\n%s\n' % (
                name, mate, index, random_seq(rng, read_len), ''.join(rng.choices(quals, k=read_len))))
    return ''.join(reads[0]), ''.join(reads[1])


def fasta_with_index(records, width=60):
    """FASTA text and the matching samtools .fai."""
    text, fai, offset = [], [], 0
    for name, seq in records:
        header = '>%s\n' % name
        lines = ''.join(seq[i:i + width] + '\n' for i in range(0, len(seq), width))
        fai.append('%s\t%d\t%d\t%d\t%d\n' % (name, len(seq), offset + len(header), width, width + 1))
        text.append(header + lines)
        offset += len(header) + len(lines)
    return ''.join(text), ''.join(fai)


def digest_of(path, algorithm):
    with open(path, 'rb') as f:
        return hashlib.new(algorithm, f.read()).hexdigest()


def sha256_of(path):
    return digest_of(path, 'sha256')


def md5_listing(tree, rels, prefix):
    return ''.join('%s  %s\n' % (digest_of(tree.path(rel), 'md5'), os.path.relpath(rel, prefix))
                   for rel in rels if os.path.isfile(tree.path(rel)))


INK, BLUE, RED, GREY = (52, 58, 64), (13, 110, 253), (220, 53, 69), (173, 181, 189)


def png(width, height, draw):
    """A truecolour PNG; `draw` is handed a rect(x0, y0, x1, y1, rgb) painter."""
    pixels = bytearray(b'\xff' * (width * height * 3))

    def rect(x0, y0, x1, y1, rgb):
        x0, x1 = max(0, x0), min(width, x1)
        row = bytes(rgb) * max(0, x1 - x0)
        for y in range(max(0, y0), min(height, y1)):
            start = (y * width + x0) * 3
            pixels[start:start + len(row)] = row

    draw(rect)
    stride = width * 3
    raw = b''.join(b'\x00' + bytes(pixels[y * stride:(y + 1) * stride]) for y in range(height))

    def chunk(tag, body):
        return (struct.pack('>I', len(body)) + tag + body
                + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def bar_chart(values, width=360, height=200):
    top = max(values) or 1

    def draw(rect):
        rect(30, 10, 32, height - 20, INK)
        rect(30, height - 22, width - 10, height - 20, INK)
        slot = (width - 50) // len(values)
        for i, value in enumerate(values):
            bar = int((height - 40) * value / top)
            x = 40 + i * slot
            rect(x, height - 22 - bar, x + slot - 10, height - 22, BLUE)
    return png(width, height, draw)


def scatter(points, width=360, height=260):
    """points are (x, y, highlighted) with x and y in 0..1."""
    def draw(rect):
        rect(30, 10, 32, height - 20, INK)
        rect(30, height - 22, width - 10, height - 20, INK)
        for x, y, hit in points:
            px, py = 34 + int(x * (width - 48)), height - 24 - int(y * (height - 36))
            rect(px - 2, py - 2, px + 3, py + 3, RED if hit else GREY)
    return png(width, height, draw)


class Tree:
    """Writes sample content under one directory, never overwriting.

    Re-running the seed keeps whatever has since been uploaded, renamed or
    edited. Files this run did create are backdated across the share's
    lifetime, so listings show a spread of modified dates, not all "just now".
    """

    def __init__(self, root, seed, created, updated):
        self.root = root.rstrip(os.sep)
        self.rng = random.Random(seed)
        self.span = (created.timestamp(), updated.timestamp())
        self.new_files = []

    def path(self, rel):
        return os.path.join(self.root, rel)

    def exists(self, rel):
        return os.path.lexists(self.path(rel))

    def dir(self, rel):
        os.makedirs(self.path(rel), exist_ok=True)

    def write(self, rel, data):
        """`data` is bytes, text, or a callable producing either, which is
        only called when the file has to be written."""
        path = self.path(rel)
        if os.path.lexists(path):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = data() if callable(data) else data
        with open(path, 'wb') as f:
            f.write(data.encode() if isinstance(data, str) else data)
        self.new_files.append(path)

    def link(self, rel, target):
        path = self.path(rel)
        if not os.path.lexists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.symlink(target, path)

    def backdate(self):
        start, end = self.span
        dir_times = {}
        for path in self.new_files:
            when = start + self.rng.random() * max(end - start, 0)
            os.utime(path, (when, when))
            parent = os.path.dirname(path)
            while parent.startswith(self.root):
                dir_times[parent] = max(dir_times.get(parent, when), when)
                if parent == self.root:
                    break
                parent = os.path.dirname(parent)
        for path, when in dir_times.items():
            os.utime(path, (when, when))


RNASEQ_SAMPLES = [('CTRL_1', 'control', 1, 'ATTACTCG+AGGCTATA'), ('CTRL_2', 'control', 2, 'TCCGGAGA+GCCTCTAT'),
                  ('CTRL_3', 'control', 3, 'CGCTCATT+AGGATAGG'), ('HEAT_1', 'heat', 1, 'GAGATTCC+TCAGAGCC'),
                  ('HEAT_2', 'heat', 2, 'ATTCAGAA+CTTCGCCT'), ('HEAT_3', 'heat', 3, 'GAATTCGT+TAAGATTA')]


def build_rnaseq(t):
    pairs, fastqs = 300, []
    for i, (sample, condition, rep, index) in enumerate(RNASEQ_SAMPLES, start=1):
        r1, r2 = ('raw_data/fastq/%s_S%d_L001_R%d_001.fastq.gz' % (sample, i, read) for read in (1, 2))
        if not (t.exists(r1) and t.exists(r2)):
            reads = fastq_pair(t.rng, pairs, index=index)
            t.write(r1, gz(reads[0]))
            t.write(r2, gz(reads[1]))
        fastqs += [r1, r2]
    undetermined = ['raw_data/fastq/Undetermined_S0_L001_R%d_001.fastq.gz' % read for read in (1, 2)]
    if not all(t.exists(rel) for rel in undetermined):
        reads = fastq_pair(t.rng, 4000, index='NNNNNNNN+NNNNNNNN')
        for rel, text in zip(undetermined, reads):
            t.write(rel, gz(text))
    fastqs += undetermined
    t.write('raw_data/md5sums.txt', lambda: md5_listing(t, fastqs, 'raw_data'))
    t.write('sample_sheet.csv', 'sample_id,condition,replicate,index,library_prep\n' + ''.join(
        '%s,%s,%d,%s,TruSeq stranded mRNA\n' % (s, c, r, i) for s, c, r, i in RNASEQ_SAMPLES))
    t.write('README.md', lambda: (
        '# Heat stress time course: RNA-seq\n\n'
        'Delivered by the Genomics Core to the Chen Lab. All reads are synthetic seed data.\n\n'
        '| Sample | Condition | Replicate | Read pairs |\n|---|---|---|---|\n'
        + ''.join('| %s | %s | %d | %d |\n' % (s, c, r, pairs) for s, c, r, _ in RNASEQ_SAMPLES)
        + '\n## Layout\n\n'
          '- `raw_data/fastq/`: paired-end 150 bp reads, one pair per sample\n'
          '- `analysis/`: QC and alignment summaries\n'
          '- `results/`: gene counts and differential expression\n\n'
          '## Checking a download\n\n```\ncd raw_data\nmd5sum -c md5sums.txt\n```\n\n'
          '![Read pairs per sample](figures/reads_per_sample.png)\n'))
    t.write('figures/reads_per_sample.png', lambda: bar_chart(
        [pairs * t.rng.uniform(0.8, 1.2) for _ in RNASEQ_SAMPLES]))
    t.write('analysis/qc/fastqc_summary.tsv', lambda: 'sample\ttotal_sequences\tpercent_gc\tpercent_duplicates\tstatus\n' + ''.join(
        '%s\t%d\t%.1f\t%.1f\t%s\n' % (s, pairs * 2, t.rng.uniform(42, 46), t.rng.uniform(8, 30),
                                      'warn' if s == 'HEAT_2' else 'pass') for s, *_ in RNASEQ_SAMPLES))
    t.write('analysis/qc/multiqc_report.html', (
        '<!doctype html>\n<html><head><meta charset="utf-8"><title>MultiQC report</title></head><body>\n'
        '<h1>MultiQC report (seed placeholder)</h1>\n<table border="1"><tr><th>Sample</th><th>Status</th></tr>\n'
        + ''.join('<tr><td>%s</td><td>%s</td></tr>\n' % (s, 'warn' if s == 'HEAT_2' else 'pass')
                  for s, *_ in RNASEQ_SAMPLES) + '</table>\n</body></html>\n'))
    for sample, *_ in RNASEQ_SAMPLES:
        t.write('analysis/alignment/%s.flagstat.txt' % sample, lambda: (
            '%d + 0 in total (QC-passed reads + QC-failed reads)\n%d + 0 mapped (%.2f%% : N/A)\n'
            '%d + 0 properly paired\n' % (pairs * 2, pairs * 2 * 0.95, 95.0, pairs * 2 * 0.92)))
    genes = ['AT%dG%05d' % (t.rng.randint(1, 5), t.rng.randrange(10, 80000, 10)) for _ in range(60)]
    heat_effect = {gene: (2 ** t.rng.uniform(1.5, 4) if i < 8 else 2 ** t.rng.gauss(0, 0.3))
                   for i, gene in enumerate(genes)}
    counts = {}
    for gene in genes:
        base = t.rng.lognormvariate(5, 1.2)
        counts[gene] = [max(0, int(t.rng.gauss(base * (heat_effect[gene] if c == 'heat' else 1), base * 0.15)))
                        for _, c, _, _ in RNASEQ_SAMPLES]
    t.write('results/counts/gene_counts.tsv', 'gene_id\t' + '\t'.join(s for s, *_ in RNASEQ_SAMPLES) + '\n' + ''.join(
        '%s\t%s\n' % (gene, '\t'.join(map(str, counts[gene]))) for gene in genes))
    de_rows, points = [], []
    for i, gene in enumerate(genes):
        lfc = round(math.log2(heat_effect[gene]), 3)
        pvalue = 10 ** -t.rng.uniform(6, 15) if i < 8 else 10 ** -t.rng.uniform(0, 2)
        de_rows.append('%s\t%.1f\t%.3f\t%.3f\t%.3g\t%.3g\n' % (
            gene, sum(counts[gene]) / 6, lfc, t.rng.uniform(0.1, 0.4), pvalue, min(1, pvalue * len(genes))))
        points.append(((lfc + 4) / 8, min(1, -math.log10(pvalue) / 15), i < 8))
    t.write('results/differential_expression/HEAT_vs_CTRL.deseq2.tsv',
            'gene_id\tbaseMean\tlog2FoldChange\tlfcSE\tpvalue\tpadj\n' + ''.join(de_rows))
    t.write('results/differential_expression/volcano.png', lambda: scatter(points))
    t.write('results/differential_expression/README.md',
            '# HEAT vs CTRL\n\nDESeq2, default settings. 8 genes pass padj < 0.05; all are '
            'heat induced.\n\n![Volcano plot](volcano.png)\n')
    t.write('docs/Méthodes – préparation des banques.txt',
            'Protocole TruSeq stranded mRNA, 500 ng ARN total, 13 cycles de PCR.\n')
    t.write('docs/meeting notes (final v2).txt',
            'Decided: keep HEAT_2 despite the duplication warning. Rerun DE without it as a check.\n')
    t.dir('scratch')


def build_wgs(t):
    samples = ['HG002', 'HG003', 'HG004']
    t.write('README.md', '# Core WGS pipeline validation\n\nGIAB trio, chr20 only. The BAM and index '
                         'files are random placeholder bytes of realistic size, not real alignments.\n')
    for sample, megabytes in zip(samples, (20, 2, 2)):
        t.write('bam/%s.chr20.bam' % sample, lambda: t.rng.randbytes(megabytes * 1024 * 1024))
        t.write('bam/%s.chr20.bam.bai' % sample, lambda: t.rng.randbytes(64 * 1024))

    def vcf():
        lines = ['##fileformat=VCFv4.2', '##source=seed_dev (synthetic)', '##contig=<ID=chr20,length=64444167>',
                 '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">',
                 '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                 '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t' + '\t'.join(samples)]
        for pos in sorted(t.rng.sample(range(60000, 64000000), 300)):
            ref, alt = t.rng.sample('ACGT', 2)
            lines.append('chr20\t%d\t.\t%s\t%s\t%.1f\tPASS\tDP=%d\tGT\t%s' % (
                pos, ref, alt, t.rng.uniform(30, 900), t.rng.randint(60, 120),
                '\t'.join(t.rng.choice(['0/1', '1/1', '0/0']) for _ in samples)))
        return gz('\n'.join(lines) + '\n')
    t.write('vcf/trio.chr20.vcf.gz', vcf)
    t.write('vcf/trio.chr20.vcf.gz.tbi', lambda: t.rng.randbytes(8 * 1024))
    t.write('targets/chr20_targets.bed', lambda: ''.join(
        'chr20\t%d\t%d\n' % (start, start + t.rng.randint(100, 400))
        for start in sorted(t.rng.sample(range(60000, 64000000), 120))))
    t.write('qc/coverage_summary.tsv', lambda: 'sample\tmean_depth\tpct_20x\n' + ''.join(
        '%s\t%.1f\t%.1f\n' % (s, t.rng.uniform(32, 38), t.rng.uniform(96, 99)) for s in samples))
    t.write('pipeline/config.yaml', 'pipeline: germline-wgs\nversion: 4.2.1\nreference: GRCh38_analysis_set\n'
                                    'caller: deepvariant\nregions: targets/chr20_targets.bed\n')
    t.write('pipeline/logs/run_2026-07-18.log', '[INFO] align: 3 samples\n[INFO] call: chr20\n'
                                                '[WARN] HG004: 0.4% reads unmapped mates\n[INFO] done\n')


def build_methylation(t):
    samples = ['WT_rep1', 'WT_rep2', 'met1_rep1', 'met1_rep2']
    t.write('README.md', '# 2019 Methylation Project\n\nArchived. This share is **read-only**: nobody '
                         'can upload or delete, whatever their permissions say.\n')
    levels = []
    for sample in samples:
        level = t.rng.uniform(0.05, 0.12) if sample.startswith('met1') else t.rng.uniform(0.25, 0.32)
        levels.append(level)

        def coverage(level=level):
            rows = []
            for start in sorted(t.rng.sample(range(1, 30000000), 1500)):
                total = t.rng.randint(5, 40)
                methylated = sum(t.rng.random() < level for _ in range(total))
                rows.append('Chr1\t%d\t%d\t%.2f\t%d\t%d\n' % (start, start, 100 * methylated / total,
                                                              methylated, total - methylated))
            return gz(''.join(rows))
        t.write('bismark/%s.deduplicated.bismark.cov.gz' % sample, coverage)
        t.write('reports/%s_PE_report.txt' % sample,
                'Bismark report for %s\nC methylated in CpG context: %.1f%%\n' % (sample, 100 * level))
    t.write('manuscript/figure_2_global_methylation.png', lambda: bar_chart(levels))
    t.write('manuscript/supplementary_table_S3.tsv', 'sample\tglobal_cpg_methylation\n' + ''.join(
        '%s\t%.3f\n' % pair for pair in zip(samples, levels)))


def build_reference(t):
    def genome():
        return fasta_with_index([('chr%d' % n, random_seq(t.rng, 20000)) for n in (1, 2, 3)])
    if not t.exists('genomes/demo_genome_v1.fa'):
        text, fai = genome()
        t.write('genomes/demo_genome_v1.fa', text)
        t.write('genomes/demo_genome_v1.fa.fai', fai)
    t.write('annotation/demo_genome_v1.gtf', lambda: ''.join(
        'chr%d\tseed\tgene\t%d\t%d\t.\t+\t.\tgene_id "DEMO%03d"; gene_name "demo%d";\n'
        % (1 + i // 10, 100 + (i % 10) * 1900, 1500 + (i % 10) * 1900, i, i) for i in range(30)))
    t.write('README.md', '# Public reference genomes\n\nThis share is public: no login is needed to view '
                         'or download.\n\n| File | Contents |\n|---|---|\n'
                         '| `genomes/demo_genome_v1.fa` | 3 synthetic chromosomes, 20 kb each |\n'
                         '| `annotation/demo_genome_v1.gtf` | 30 synthetic genes |\n')
    t.write('LICENSE.txt', 'Synthetic data generated for development. No restrictions.\n')
    t.write('checksums.sha256', lambda: ''.join(
        '%s  %s\n' % (sha256_of(t.path(rel)), rel)
        for rel in ('genomes/demo_genome_v1.fa', 'annotation/demo_genome_v1.gtf') if t.exists(rel)))


def build_plates(t):
    rows, plates = 'ABCDEFGH', (1, 2, 3)
    t.write('README.md', '# Amplicon plate reads\n\nOne FASTQ per well. Use search to find a well, '
                         'e.g. `C07`.\n')
    t.write('plate_map.csv', 'plate,well,sample,primer\n' + ''.join(
        'plate_%02d,%s%02d,S%03d,ITS1F-ITS2\n' % (p, r, c, (p - 1) * 96 + i * 12 + c)
        for p in plates for i, r in enumerate(rows) for c in range(1, 13)))
    for p in plates:
        for r in rows:
            for c in range(1, 13):
                t.write('plates/plate_%02d/%s%02d.fastq' % (p, r, c),
                        lambda: fastq_pair(t.rng, 10, read_len=120)[0])


def build_consortium(t):
    isolates = [('Fo_CA_2021_014', 'California', 2021), ('Fo_CA_2021_022', 'California', 2021),
                ('Fo_AZ_2022_003', 'Arizona', 2022), ('Fo_AZ_2022_011', 'Arizona', 2022),
                ('Fo_OR_2023_007', 'Oregon', 2023)]
    t.write('README.md', '# Isolate assemblies\n\n`latest/` is a symlink to `assemblies/v2/`. Uploads '
                         'through `latest/` are refused, because it is not a real directory.\n')
    t.write('metadata/isolates.tsv', 'isolate\tspecies\thost\tsite\tyear\n' + ''.join(
        '%s\tFusarium oxysporum\tLactuca sativa\t%s\t%d\n' % i for i in isolates))
    for version, contigs in (('v1', 6), ('v2', 3)):
        for isolate, *_ in isolates:
            t.write('assemblies/%s/%s.contigs.fasta' % (version, isolate), lambda: fasta_with_index(
                [('%s_contig%d' % (isolate, n), random_seq(t.rng, t.rng.randint(2000, 5000)))
                 for n in range(1, contigs + 1)])[0])
    for isolate, *_ in isolates:
        t.write('annotation/v2/%s.gff3' % isolate, '##gff-version 3\n%s_contig1\tseed\tgene\t120\t1450\t.\t+'
                                                   '\t.\tID=%s_g1\n' % (isolate, isolate))
    t.link('latest', os.path.join('assemblies', 'v2'))


def outside_dir():
    """A directory outside DIRECTORY_WHITELIST for the locked share's symlink,
    so the app's own path check finds it and locks the share. None if every
    candidate is whitelisted or unwritable."""
    whitelist = getattr(settings, 'DIRECTORY_WHITELIST', None) or []
    for parent in OUTSIDE_PARENTS:
        path = os.path.join(parent, OUTSIDE_NAME)
        if os.path.isdir(parent) and os.access(parent, os.W_OK) and not paths_contain(whitelist, path):
            return path
    return None


def build_scratch(t):
    t.write('notes/todo.txt', '- rerun alignment with the new index\n- ask Dan about plate 3\n')
    t.write('analysis/explore.R', 'counts <- read.delim("gene_counts.tsv", row.names = 1)\n'
                                  'summary(colSums(counts))\n')
    target = outside_dir()
    if not target:
        return  # seed_shares locks the share directly instead
    os.makedirs(target, exist_ok=True)
    outside = os.path.join(target, 'not_for_sharing.txt')
    if not os.path.exists(outside):
        with open(outside, 'w') as f:
            f.write('Outside the whitelist. The share linking here should be locked.\n')
    link = t.path('shared_drive')
    if os.path.islink(link) and os.readlink(link) != target:
        os.unlink(link)  # an earlier seed pointed it somewhere now whitelisted
    t.link('shared_drive', target)


def build_run(t):
    """A sequencer run folder: the target of the linked share, not a share itself."""
    t.write('RunInfo.xml', '<?xml version="1.0"?>\n<RunInfo><Run Id="%s" Number="456">'
                           '<Flowcell>HXXXXDSX5</Flowcell><Instrument>A00123</Instrument></Run></RunInfo>\n'
            % os.path.basename(t.root))
    t.write('SampleSheet.csv', '[Data]\nSample_ID,Sample_Project,index\n' + ''.join(
        '%s,Chen_Lab,%s\n' % (s, i.split('+')[0]) for s, _, _, i in RNASEQ_SAMPLES[:3]))
    t.write('Reports/demultiplex_stats.csv', lambda: 'sample,reads\n' + ''.join(
        '%s,%d\n' % (s, t.rng.randint(20000000, 30000000)) for s, *_ in RNASEQ_SAMPLES[:3]))
    for sample, *_ in RNASEQ_SAMPLES[:3]:
        t.write('fastq/Chen_Lab/%s_R1_001.fastq.gz' % sample, lambda: gz(fastq_pair(t.rng, 50)[0]))
    t.write('CopyComplete.txt', '')


LAYOUTS = {'rnaseq': build_rnaseq, 'wgs': build_wgs, 'methylation': build_methylation,
           'reference': build_reference, 'plates': build_plates, 'consortium': build_consortium,
           'scratch': build_scratch}


# --- the command ------------------------------------------------------------

class Command(BaseCommand):
    help = ('Seed the development database with users, groups and shares, and build the '
            'share directories to match. Refuses to run unless DEBUG is on.')

    def add_arguments(self, parser):
        parser.add_argument('--path', help='Directory to hold the seed filesystems. Default: '
                                           '"dev-seed" inside FILESYSTEM_DIRECTORIES[0].')
        parser.add_argument('--password', default=DEFAULT_PASSWORD,
                            help='Password for every seeded account. Default: %(default)s')
        parser.add_argument('--reset', action='store_true',
                            help='First delete the seeded users, groups, filesystems and messages, '
                                 'plus every share owned by a seeded user or stored on a seeded '
                                 'filesystem (and their subshares), files included. Lists them and '
                                 'asks first.')
        parser.add_argument('--noinput', '--no-input', action='store_false', dest='interactive',
                            help='Do not ask before --reset deletes anything.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Refusing to seed with DEBUG off: every seeded account shares one '
                               'known password.')
        validate_specs()
        os.umask(settings.UMASK)
        self.now = timezone.now()
        root = self.resolve_root(options['path'])
        self.check_group_names()
        if options['reset']:
            self.reset(options['interactive'])
        self.users = self.seed_users(options['password'])
        self.filesystems = self.seed_filesystems(root)
        self.groups = self.seed_groups()
        self.footers = self.seed_footers()
        self.filepath = self.seed_link_target()
        shares = self.seed_shares()
        self.seed_messages()
        self.summarise(root, options['password'], shares)

    def days_ago(self, days):
        return self.now - timedelta(days=days)

    def note(self, message):
        self.stdout.write(self.style.WARNING(message))

    # -- checks ----------------------------------------------------------------

    def resolve_root(self, path):
        if not path:
            directories = getattr(settings, 'FILESYSTEM_DIRECTORIES', None) or []
            if not directories:
                raise CommandError('FILESYSTEM_DIRECTORIES is empty, so there is no default '
                                   'location for the seed. Pass --path.')
            path = os.path.join(directories[0], 'dev-seed')
        path = os.path.abspath(path)
        whitelist = getattr(settings, 'DIRECTORY_WHITELIST', None) or []
        if not paths_contain(whitelist, path):
            raise CommandError('%s is not inside DIRECTORY_WHITELIST %s. The app refuses to list '
                               'shares outside it.' % (path, whitelist))
        roots = getattr(settings, 'SENDFILE_ROOTS', None) or []
        if roots and not paths_contain(roots, path):
            self.note('%s is not inside SENDFILE_ROOTS, so downloads from seeded shares will 404.' % path)
        return path

    def check_group_names(self):
        """Never adopt a group the seed didn't make: re-running resets its
        members, and --reset deletes it."""
        seed_usernames = [spec['email'] for spec in USERS.values()]
        for spec in GROUPS:
            group = Group.objects.filter(name=spec['name']).first()
            if group and not GroupProfile.objects.filter(
                    group=group, created_by__username__in=seed_usernames).exists():
                raise CommandError('A group named "%s" already exists and was not made by this '
                                   'command. Rename it, or rename it in GROUPS in %s.'
                                   % (spec['name'], __file__))

    # -- reset -----------------------------------------------------------------

    def reset(self, interactive):
        users = User.objects.filter(username__in=[spec['email'] for spec in USERS.values()])
        group_pks = list(Group.objects.filter(name__in=[spec['name'] for spec in GROUPS],
                                              profile__created_by__in=users).values_list('pk', flat=True))
        filesystems = Filesystem.objects.filter(name__in=[spec['name'] for spec in FILESYSTEMS.values()])
        filepaths = FilePath.objects.filter(name=FILEPATH_NAME)
        messages = Message.objects.none()
        for spec in MESSAGES:
            messages |= Message.objects.filter(title=spec['title'], description=spec['description'])
        seed_ids = {spec['id'] for spec in SHARES}
        ids = set(Share.objects.filter(Q(id__in=seed_ids) | Q(owner__in=users) | Q(filesystem__in=filesystems)
                                       | Q(filepath__in=filepaths)).values_list('id', flat=True))
        while True:  # subshares of anything going, whoever owns them
            children = set(Share.objects.filter(parent_id__in=ids).exclude(id__in=ids)
                           .values_list('id', flat=True))
            if not children:
                break
            ids |= children
        shares = list(Share.objects.filter(id__in=ids).select_related('filesystem'))

        counts = [(users.count(), 'users'), (len(group_pks), 'groups'), (len(shares), 'shares'),
                  (filesystems.count(), 'filesystems'), (messages.count(), 'messages')]
        if not any(n for n, _ in counts):
            self.stdout.write('Nothing to reset.')
            return
        self.stdout.write('--reset will delete ' + ', '.join('%d %s' % c for c in counts) + '.')
        extra = [s for s in shares if s.id not in seed_ids]
        if extra:
            self.stdout.write('Including %d shares made after seeding, with their files:' % len(extra))
            for share in extra:
                self.stdout.write('  %s  %s  (%s)' % (share.id, share.name, share.get_path()))
        if interactive and input("Type 'yes' to continue: ") != 'yes':
            raise CommandError('Reset cancelled. Nothing was deleted.')

        # Delete rows inside one transaction with the share signal disconnected,
        # then touch the disk only once that has committed, so a refused
        # delete can't leave rows whose directories are already gone.
        post_delete.disconnect(share_post_delete, sender=Share)
        try:
            with transaction.atomic():
                remaining = {s.id for s in shares}
                while remaining:  # Share.parent is RESTRICT: children first
                    parents = set(Share.objects.filter(id__in=remaining, parent_id__in=remaining)
                                  .values_list('parent_id', flat=True))
                    leaves = remaining - parents
                    Share.objects.filter(id__in=leaves).delete()
                    remaining -= leaves
                ShareLog.objects.filter(user__in=users).update(user=None)
                UserProfile.objects.filter(created_by__in=users).update(created_by=None)
                # guardian's generic per-object rows (manage_group) have no FK to
                # the group, so nothing cascades to them.
                UserObjectPermission.objects.filter(content_type=ContentType.objects.get_for_model(Group),
                                                    object_pk__in=[str(pk) for pk in group_pks]).delete()
                GroupProfile.objects.filter(group__in=group_pks).delete()
                Group.objects.filter(pk__in=group_pks).delete()
                users.delete()
                filepaths.delete()
                filesystems.delete()
                messages.delete()
        except (ProtectedError, RestrictedError) as e:
            raise CommandError('Reset aborted, nothing was deleted: %s' % e)
        finally:
            post_delete.connect(share_post_delete, sender=Share)

        for share in sorted(shares, key=lambda s: not os.path.islink(s.get_path())):
            try:
                share_post_delete(Share, share)
            except Exception as e:
                self.note('Could not remove %s: %s' % (share.get_path(), e))
        link_root = self.link_root()
        outside = [os.path.join(parent, OUTSIDE_NAME) for parent in OUTSIDE_PARENTS]
        for path in filter(None, outside + [link_root]):
            shutil.rmtree(path, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS('Reset done.'))

    # -- seeding ---------------------------------------------------------------

    def seed_users(self, password):
        hashed = make_password(password)  # once, not once per user: PBKDF2 is slow on purpose
        share_ct = ContentType.objects.get_for_model(Share)
        global_perms = {p.codename: p for p in Permission.objects.filter(
            content_type=share_ct, codename__in=['add_share', 'link_to_path'])}
        users = {}
        for handle, spec in USERS.items():
            user = User.objects.filter(username=spec['email']).first() or User(username=spec['email'])
            user.email = spec['email']
            user.first_name = spec.get('first_name', '')
            user.last_name = spec.get('last_name', '')
            user.is_superuser = spec.get('is_superuser', False)
            user.is_staff = spec.get('is_staff', False)
            user.is_active = spec.get('is_active', True)
            user.date_joined = self.days_ago(spec['joined'])
            user.last_login = None if spec['last_login'] is None else self.days_ago(spec['last_login'])
            user.password = hashed
            user.save()
            user.user_permissions.set([global_perms[c] for c in spec.get('perms', [])])
            users[handle] = user
        for handle, spec in USERS.items():
            UserProfile.objects.update_or_create(
                user=users[handle], defaults={'created_by': users.get(spec.get('created_by'))})
        return users

    def seed_filesystems(self, root):
        filesystems = {}
        for key, spec in FILESYSTEMS.items():
            path = os.path.join(root, spec['subdir'])
            fs = Filesystem.objects.filter(name=spec['name']).first()
            if fs and os.path.normpath(fs.path) != path:
                raise CommandError('Filesystem "%s" is already seeded at %s, not %s. Pass --path %s, or '
                                   'use --reset to move the seed.' % (spec['name'], fs.path, path,
                                                                      os.path.dirname(fs.path)))
            fs = fs or Filesystem(name=spec['name'])
            fs.path, fs.description, fs.type = path, spec['description'], Filesystem.TYPE_STANDARD
            fs.save()
            os.makedirs(path, exist_ok=True)
            wanted = [self.users[h] for h in spec['users']]
            fs.users.remove(*[u for u in self.users.values() if u not in wanted])
            fs.users.add(*wanted)
            filesystems[key] = fs
        return filesystems

    def seed_groups(self):
        groups = {}
        for spec in GROUPS:
            group, _ = Group.objects.get_or_create(name=spec['name'])
            GroupProfile.objects.update_or_create(group=group, defaults={
                'created_by': self.users[spec['created_by']], 'description': spec['description']})
            group.user_set.set([self.users[h] for h in spec['members']])
            for handle in spec['members']:
                if handle in spec['managers']:
                    assign_perm('manage_group', self.users[handle], group)
                else:
                    remove_perm('manage_group', self.users[handle], group)
            groups[spec['name']] = group
        return groups

    def seed_footers(self):
        footers = {}
        for spec in sorted(EMAIL_FOOTERS, key=lambda s: s['is_default']):  # one default per group
            group = self.groups[spec['group']]
            if spec['is_default']:
                EmailFooter.objects.filter(group=group, is_default=True).exclude(
                    title=spec['title']).update(is_default=False)
            footers[(spec['group'], spec['title'])] = EmailFooter.objects.update_or_create(
                group=group, title=spec['title'],
                defaults={'content': spec['content'], 'is_default': spec['is_default']})[0]
        return footers

    def link_root(self):
        directories = getattr(settings, 'LINK_TO_DIRECTORIES', None) or []
        return os.path.join(directories[0], LINK_DIR_NAME) if directories else None

    def seed_link_target(self):
        link_root = self.link_root()
        if not link_root:
            self.note('LINK_TO_DIRECTORIES is empty: skipping the linked share and its FilePath.')
            return None
        try:
            for run in LINKED_RUNS:
                tree = Tree(os.path.join(link_root, run), run, self.days_ago(24), self.days_ago(23))
                build_run(tree)
                tree.backdate()
        except OSError as e:
            self.note('Cannot write to %s (%s): skipping the linked share.' % (link_root, e))
            return None
        fp = FilePath.objects.filter(name=FILEPATH_NAME).first() or FilePath(name=FILEPATH_NAME)
        fp.path = link_root
        fp.description = 'Run folders written by seed_dev. Only folders named like a run can be linked.'
        fp.regexes = [re.escape(link_root) + r'/\d{6}_A\d{5}_\d{4}_[AB][A-Z0-9]{9}/?$']
        fp.show_path = True
        fp.save()
        fp.users.add(self.users['maria'], self.users['bob'])
        return fp

    def seed_shares(self):
        shares = {}
        for spec in SHARES:
            if spec.get('linked') and not self.filepath:
                continue
            share, created = self.upsert_share(spec, shares)
            shares[share.id] = (share, spec)
            share.set_tags(spec.get('tags', []))
            for handle, perms in spec.get('users', {}).items():
                self.sync_perms(share, self.users[handle], perms)
            for name, perms in spec.get('groups', {}).items():
                self.sync_perms(share, self.groups[name], perms)
            path = share.get_path()
            if spec.get('missing'):
                if os.path.isdir(path) and not os.listdir(path):
                    os.rmdir(path)
                elif os.path.exists(path):
                    self.note('%s should be missing but holds files; leaving it.' % path)
            elif spec.get('layout'):
                tree = Tree(path, spec['id'], self.days_ago(spec['created']), self.days_ago(spec['updated']))
                LAYOUTS[spec['layout']](tree)
                tree.backdate()
            for subpath, notes, tags in spec.get('metadata', []):
                if share.get_path_type(subpath):
                    metadata = MetaData.objects.get_or_create(share=share, subpath=subpath)[0]
                    metadata.notes = notes
                    metadata.save()
                    metadata.tags.set([Tag.objects.get_or_create(name=tag)[0] for tag in tags])
            if created:  # logs only once, or every re-run would repeat them
                for days, handle, action, text, paths in spec.get('logs', []):
                    log = ShareLog.objects.create(share=share, user=self.users[handle], action=action,
                                                  text=text, paths=paths)
                    ShareLog.objects.filter(pk=log.pk).update(timestamp=self.days_ago(days))

        # With every directory in place, let the app check them as it would
        # (this is what locks the illegal symlink), then size and backdate.
        for share, spec in shares.values():
            share.check_paths(check_symlinks=True)
            if share.locked and not spec.get('expect_locked'):
                self.note('%s was locked by the path check: %s' % (share.id, '; '.join(
                    '%s -> %s: %s' % (l['path'], l['target'], l['error'])
                    for l in share.meta.get('symlinks', []) if l['error'])))
            if spec.get('expect_locked') and not share.locked:
                self.note('%s was not locked by the path check, because no directory outside '
                          'DIRECTORY_WHITELIST could be linked to (tried %s); locking it directly.'
                          % (share.id, ', '.join(OUTSIDE_PARENTS)))
                share.locked = True
                share.save()
            if share.path_exists and not share.parent:
                try:
                    share.get_stats()
                except Exception as e:
                    self.note('Could not size %s: %s' % (share.id, e))
            Share.objects.filter(pk=share.pk).update(
                created=self.days_ago(spec['created']), updated=self.days_ago(spec['updated']),
                last_data_access=self.days_ago(spec['accessed']) if 'accessed' in spec else None)
        return [share for share, _ in shares.values()]

    def upsert_share(self, spec, shares):
        share = Share.objects.filter(id=spec['id']).first()
        created = share is None
        share = share or Share(id=spec['id'])
        share.name = spec['name']
        share.notes = spec.get('notes')
        share.owner = self.users[spec['owner']]
        share.secure = spec.get('secure', True)
        share.read_only = spec.get('read_only', False)
        share.locked = False  # the path check re-locks the one that should be
        footer = spec.get('footer')
        share.email_footer = self.footers[footer] if footer else None
        slug = spec.get('slug')
        if slug and Share.objects.filter(slug=slug).exclude(id=spec['id']).exists():
            self.note('Slug "%s" is taken by another share; %s gets none.' % (slug, spec['id']))
            slug = None
        share.slug = slug
        if spec.get('parent'):
            parent = shares[spec['parent']][0]
            share.parent = parent
            share.filesystem = parent.filesystem
            share.sub_directory = spec['sub_directory']
            share.link_to_path = os.path.join(parent.get_path(), spec['sub_directory'])
            share.read_only = share.read_only or parent.read_only
        elif spec.get('linked'):
            share.filesystem = self.filesystems[spec.get('filesystem', 'primary')]
            share.filepath = self.filepath
            share.link_to_path = os.path.join(self.filepath.path, LINKED_RUNS[0])
        else:
            share.filesystem = self.filesystems[spec.get('filesystem', 'primary')]
        share.save()  # a new share's post_save signal makes its directory or symlink
        return share, created

    def sync_perms(self, share, principal, wanted):
        if isinstance(principal, Group):
            rows = ShareGroupObjectPermission.objects.filter(content_object=share, group=principal)
        else:
            rows = ShareUserObjectPermission.objects.filter(content_object=share, user=principal)
        current = set(rows.values_list('permission__codename', flat=True))
        for perm in current - set(wanted):
            remove_perm(perm, principal, share)
        for perm in set(wanted) - current:
            assign_perm(perm, principal, share)

    def seed_messages(self):
        for spec in MESSAGES:
            message = (Message.objects.filter(title=spec['title'], description=spec['description']).first()
                       or Message(title=spec['title'], description=spec['description']))
            message.active = spec['active']
            message.expires = ((self.now + timedelta(days=spec['expires_in'])).date()
                               if 'expires_in' in spec else None)
            message.save()
            viewed = [self.users[h] for h in spec.get('viewed_by', [])]
            message.viewed_by.remove(*[u for u in self.users.values() if u not in viewed])
            message.viewed_by.add(*viewed)
            Message.objects.filter(pk=message.pk).update(created=self.days_ago(spec['created']))

    def summarise(self, root, password, shares):
        site = getattr(settings, 'SITE_URL', '').rstrip('/')
        self.stdout.write(self.style.SUCCESS(
            '\nSeeded %d users, %d groups and %d shares under %s'
            % (len(self.users), len(self.groups), len(shares), root)))
        self.stdout.write('Every account\'s password: %s\n' % password)
        for handle, spec in USERS.items():
            self.stdout.write('  %-28s %s' % (spec['email'], spec['role']))
        self.stdout.write('')
        for share in shares:
            share.refresh_from_db()
            flags = [label for label, on in (('read-only', share.read_only), ('public', not share.secure),
                                             ('locked', share.locked), ('missing', not share.path_exists),
                                             ('subshare', share.parent_id),
                                             ('linked', share.link_to_path and not share.parent_id)) if on]
            self.stdout.write('  %s%s\n      %s (%s)%s' % (
                site, share.get_url(), share.name, share.owner.username,
                '  [%s]' % ', '.join(flags) if flags else ''))


def validate_specs():
    """Catch a bad edit to the data above before anything is written. Names,
    notes and tags are held to the share form's own patterns, so every seeded
    share can still be saved from its edit page."""
    problems = []
    share_perms = {codename for codename, _ in Share._meta.permissions}
    actions = {value for key, value in vars(ShareLog).items() if key.startswith('ACTION_')}
    fields = ShareForm.base_fields
    group_names = {g['name'] for g in GROUPS}
    seen = set()
    for spec in SHARES:
        sid = spec['id']
        if not re.match(r'^[\da-zA-Z]{15}$', sid):
            problems.append('%s: share ids are 15 letters or digits (urls.py)' % sid)
        if sid in seen:
            problems.append('%s: duplicate id' % sid)
        if spec.get('parent') and spec['parent'] not in seen:
            problems.append('%s: parent %s must come earlier in SHARES' % (sid, spec['parent']))
        seen.add(sid)
        if not fields['name'].regex.match(spec['name']):
            problems.append('%s: the share form would reject the name' % sid)
        if spec.get('notes') and not fields['notes'].regex.match(spec['notes']):
            problems.append('%s: the share form would reject the notes' % sid)
        if spec.get('tags') and not fields['tags'].regex.match(','.join(spec['tags'])):
            problems.append('%s: the share form would reject the tags' % sid)
        if spec.get('layout') and spec['layout'] not in LAYOUTS:
            problems.append('%s: no layout "%s"' % (sid, spec['layout']))
        if spec['owner'] not in USERS:
            problems.append('%s: unknown owner %s' % (sid, spec['owner']))
        for handle, perms in spec.get('users', {}).items():
            if handle not in USERS:
                problems.append('%s: unknown user %s' % (sid, handle))
            problems += ['%s: unknown permission %s' % (sid, p) for p in perms if p not in share_perms]
        for name, perms in spec.get('groups', {}).items():
            if name not in group_names:
                problems.append('%s: unknown group %s' % (sid, name))
            problems += ['%s: unknown permission %s' % (sid, p) for p in perms if p not in share_perms]
        for _, handle, action, _, _ in spec.get('logs', []):
            if action not in actions:
                problems.append('%s: "%s" is not a ShareLog action' % (sid, action))
            if handle not in USERS:
                problems.append('%s: unknown log user %s' % (sid, handle))
    for spec in GROUPS:
        for handle in spec['members'] + spec['managers'] + [spec['created_by']]:
            if handle not in USERS:
                problems.append('group %s: unknown user %s' % (spec['name'], handle))
    for spec in MESSAGES:
        if len(spec['title']) > Message._meta.get_field('title').max_length:
            problems.append('message "%s": title too long' % spec['title'])
    if problems:
        raise CommandError('The seed data is inconsistent:\n  ' + '\n  '.join(problems))
