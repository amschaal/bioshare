"""Shared definitions for the documentation demo dataset.

`seed_docs_demo` creates everything named here; `unseed_docs_demo` deletes exactly
what is named here and nothing else. Keeping the manifest in one module is what
makes the teardown safe: it can never match a real share or a real account by
accident, because it only ever looks up these literal names and addresses.

The leading underscore keeps Django's command loader from treating this as a
management command.

Every address uses a domain reserved by RFC 2606 (`example.org`, `example.edu`),
which can never belong to a real mailbox. That matters even with a console email
backend, because these names end up in published screenshots.
"""

# --- accounts ---------------------------------------------------------------
# (username/email, first name, last name)
DEMO_USERS = [
    ('r.okafor@example.edu', 'Rachel', 'Okafor'),
    ('m.lindqvist@example.edu', 'Mikael', 'Lindqvist'),
    ('s.patel@example.edu', 'Sunita', 'Patel'),
    ('j.moreau@example.org', 'Julien', 'Moreau'),
    ('h.tanaka@example.edu', 'Hana', 'Tanaka'),
]

# --- groups -----------------------------------------------------------------
# (name, description, [member emails])
DEMO_GROUPS = [
    (
        'Okafor Lab',
        'Comparative transcriptomics group.',
        ['r.okafor@example.edu', 'h.tanaka@example.edu'],
    ),
    (
        'Sequencing Facility',
        'Staff who deliver raw sequencing runs to collaborators.',
        ['m.lindqvist@example.edu', 's.patel@example.edu'],
    ),
    (
        'Marine Metagenomics Consortium',
        'Multi-institution project sharing environmental sequencing data.',
        ['j.moreau@example.org', 'r.okafor@example.edu', 'h.tanaka@example.edu'],
    ),
]

# --- email footers ----------------------------------------------------------
# (group name, title, html content, is_default)
DEMO_EMAIL_FOOTERS = [
    (
        'Sequencing Facility',
        'Sequencing Facility sign-off',
        '<p>Sequencing Facility &middot; Room 114, Life Sciences Building<br>'
        'Questions about a run? Reply to this message.</p>',
        True,
    ),
    (
        'Okafor Lab',
        'Okafor Lab sign-off',
        '<p>Okafor Lab &middot; Department of Molecular Biology</p>',
        True,
    ),
]

# --- files ------------------------------------------------------------------
# Layouts are (relative path, approximate size in KB). Directories are implied by
# the paths. Sizes are padded with filler so the Size column shows a realistic
# spread without writing anything genuinely large.
RNASEQ_LAYOUT = [
    ('README.md', 0),  # 0 => use the literal content below
    ('samples.csv', 0),
    ('checksums.md5', 0),
    ('raw_reads/S01_L001_R1.fastq.gz', 244),
    ('raw_reads/S01_L001_R2.fastq.gz', 240),
    ('raw_reads/S02_L001_R1.fastq.gz', 251),
    ('raw_reads/S02_L001_R2.fastq.gz', 247),
    ('alignments/S01.sorted.bam', 512),
    ('alignments/S01.sorted.bam.bai', 12),
    ('alignments/S02.sorted.bam', 498),
    ('alignments/S02.sorted.bam.bai', 12),
    ('qc_reports/S01_fastqc.html', 88),
    ('qc_reports/S02_fastqc.html', 86),
    ('qc_reports/multiqc_report.html', 164),
]

RUN_DELIVERY_LAYOUT = [
    ('README.md', 0),
    ('RunInfo.xml', 4),
    ('demultiplex_stats.csv', 0),
    ('fastq/Undetermined_S0_R1.fastq.gz', 320),
    ('fastq/SampleA_S1_R1.fastq.gz', 288),
    ('fastq/SampleA_S1_R2.fastq.gz', 284),
    ('fastq/SampleB_S2_R1.fastq.gz', 296),
    ('fastq/SampleB_S2_R2.fastq.gz', 291),
    ('reports/laneBarcode.html', 46),
]

ASSEMBLY_LAYOUT = [
    ('README.md', 0),
    ('assembly/scaffolds.fasta', 640),
    ('assembly/contigs.fasta', 604),
    ('assembly/assembly_stats.txt', 2),
    ('annotation/genes.gff3', 420),
    ('annotation/proteins.faa', 380),
]

METAGENOME_LAYOUT = [
    ('README.md', 0),
    ('station_metadata.csv', 0),
    ('reads/ST01_surface_R1.fastq.gz', 380),
    ('reads/ST01_surface_R2.fastq.gz', 376),
    ('reads/ST02_deep_R1.fastq.gz', 402),
    ('reads/ST02_deep_R2.fastq.gz', 399),
    ('taxonomy/kraken2_report.txt', 128),
]

ARCHIVE_LAYOUT = [
    ('README.md', 0),
    ('2024_pilot/counts_matrix.tsv', 96),
    ('2024_pilot/design.csv', 0),
    ('2025_followup/counts_matrix.tsv', 104),
    ('2025_followup/design.csv', 0),
]

IMAGING_LAYOUT = [
    ('README.md', 0),
    ('plate01/well_A01.tif', 220),
    ('plate01/well_A02.tif', 218),
    ('plate02/well_A01.tif', 224),
    ('analysis/summary.csv', 0),
]

# File bodies that should read as real content rather than filler.
FILE_CONTENT = {
    'samples.csv': (
        'sample_id,condition,replicate,read_pairs,rin\n'
        'S01,control,1,24183991,9.1\n'
        'S02,control,2,23874120,8.8\n'
        'S03,treated,1,25017433,9.3\n'
        'S04,treated,2,24662087,9.0\n'
    ),
    'checksums.md5': (
        'd41d8cd98f00b204e9800998ecf8427e  raw_reads/S01_L001_R1.fastq.gz\n'
        'c157a79031e1c40f85931829bc5fc552  raw_reads/S01_L001_R2.fastq.gz\n'
        '9f2feb0f21b8dbd4d6a4a1b1b1e0a4f5  alignments/S01.sorted.bam\n'
    ),
    'demultiplex_stats.csv': (
        'lane,sample,barcode,reads,percent_of_lane\n'
        '1,SampleA,ATTACTCG,18442310,41.2\n'
        '1,SampleB,TCCGGAGA,19023877,42.5\n'
        '1,Undetermined,,7301442,16.3\n'
    ),
    'station_metadata.csv': (
        'station,latitude,longitude,depth_m,temperature_c,collected\n'
        'ST01,36.7783,-119.4179,5,18.4,2026-03-11\n'
        'ST02,36.9014,-119.6001,240,7.2,2026-03-12\n'
    ),
    'design.csv': (
        'sample,group,batch\n'
        'A1,control,1\n'
        'A2,control,1\n'
        'B1,treated,2\n'
        'B2,treated,2\n'
    ),
    'summary.csv': (
        'plate,well,cell_count,mean_intensity\n'
        'plate01,A01,1842,0.412\n'
        'plate01,A02,1799,0.408\n'
        'plate02,A01,1903,0.421\n'
    ),
    'assembly_stats.txt': (
        'total_scaffolds\t1284\n'
        'total_length\t42881233\n'
        'n50\t184221\n'
        'largest_scaffold\t1042118\n'
        'gc_percent\t41.2\n'
    ),
}

# --- shares -----------------------------------------------------------------
# owner: 'docs' means the account the screenshots are taken with, so the share
# shows up under "My latest shares". Any other value is a demo user's email, and
# the docs account is given access instead, which populates "Recently shared
# with me".
DEMO_SHARES = [
    {
        'name': 'Okafor Lab — RNA-seq time course',
        'slug': 'okafor-rnaseq-timecourse',
        'owner': 'docs',
        'notes': 'Paired-end RNA-seq across four time points, with alignments and '
                 'per-sample QC. Raw reads are in raw_reads/; see README.md.',
        'tags': ['rnaseq', 'timecourse', 'mouse'],
        'layout': RNASEQ_LAYOUT,
        'read_only': False,
        'user_perms': {
            'r.okafor@example.edu': ['view', 'download', 'write', 'delete'],
            'h.tanaka@example.edu': ['view', 'download'],
        },
        'group_perms': {
            'Okafor Lab': ['view', 'download', 'write', 'delete'],
            'Sequencing Facility': ['view', 'download'],
        },
        'metadata': [
            ('raw_reads', 'Delivered by the sequencing facility on 2026-03-02.',
             ['raw']),
            ('qc_reports/multiqc_report.html', 'Aggregated QC across all samples.',
             ['qc']),
        ],
    },
    {
        'name': 'NovaSeq run 240311 — delivery',
        'slug': 'novaseq-240311-delivery',
        'owner': 'docs',
        'notes': 'Demultiplexed FASTQ delivery for run 240311. Please download '
                 'promptly; deliveries are pruned after 90 days.',
        'tags': ['delivery', 'novaseq', 'fastq'],
        'layout': RUN_DELIVERY_LAYOUT,
        'read_only': True,
        'user_perms': {
            'm.lindqvist@example.edu': ['view', 'download', 'admin'],
            's.patel@example.edu': ['view', 'download'],
        },
        'group_perms': {
            'Sequencing Facility': ['view', 'download', 'admin'],
        },
        'metadata': [],
    },
    {
        'name': 'Draft genome assembly — C. elegans isolate',
        'slug': 'celegans-draft-assembly',
        'owner': 'docs',
        'notes': 'Draft assembly and structural annotation. Scaffolds are not yet '
                 'polished; do not use for publication figures.',
        'tags': ['assembly', 'annotation', 'draft'],
        'layout': ASSEMBLY_LAYOUT,
        'read_only': False,
        'user_perms': {
            's.patel@example.edu': ['view', 'download', 'write'],
        },
        'group_perms': {},
        'metadata': [
            ('assembly/scaffolds.fasta', 'Primary scaffolds, 1284 sequences.',
             ['fasta']),
        ],
    },
    {
        'name': 'Marine metagenomes — spring survey',
        'slug': 'marine-metagenomes-spring',
        'owner': 'j.moreau@example.org',
        'notes': 'Environmental sequencing from the spring survey, two stations. '
                 'Station metadata accompanies the reads.',
        'tags': ['metagenomics', 'marine', 'survey'],
        'layout': METAGENOME_LAYOUT,
        'read_only': False,
        'user_perms': {'docs': ['view', 'download']},
        'group_perms': {
            'Marine Metagenomics Consortium': ['view', 'download', 'write', 'delete'],
        },
        'metadata': [],
    },
    {
        'name': 'Differential expression archive 2024–2025',
        'slug': 'de-archive-2024-2025',
        'owner': 'r.okafor@example.edu',
        'notes': 'Count matrices and designs for the pilot and follow-up '
                 'experiments. Read only — archived.',
        'tags': ['archive', 'counts', 'rnaseq'],
        'layout': ARCHIVE_LAYOUT,
        'read_only': True,
        'user_perms': {'docs': ['view', 'download']},
        'group_perms': {'Okafor Lab': ['view', 'download']},
        'metadata': [],
    },
    {
        'name': 'High-content imaging — plate screen',
        'slug': 'imaging-plate-screen',
        'owner': 'h.tanaka@example.edu',
        'notes': 'Well-level TIFFs from the two-plate pilot screen, plus the '
                 'summarised cell counts.',
        'tags': ['imaging', 'screen'],
        'layout': IMAGING_LAYOUT,
        'read_only': False,
        'user_perms': {'docs': ['view', 'download', 'share_read_only']},
        'group_perms': {},
        'metadata': [],
    },
]

# Short names used in the manifest above -> Share.PERMISSION_* attribute names.
PERMISSION_ALIASES = {
    'view': 'PERMISSION_VIEW',
    'download': 'PERMISSION_DOWNLOAD',
    'write': 'PERMISSION_WRITE',
    'delete': 'PERMISSION_DELETE',
    'admin': 'PERMISSION_ADMIN',
    'share_read_only': 'PERMISSION_SHARE_READ_ONLY',
    'link_to_path': 'PERMISSION_LINK_TO_PATH',
}

# --- SSH key ----------------------------------------------------------------
# So the "SSH public keys" page shows a populated list rather than its empty
# state. The private half is discarded at generation time and never stored.
DEMO_SSH_KEY_NAME = 'laptop (docs demo)'

# --- activity log -----------------------------------------------------------
# (share slug, action attribute on ShareLog, text, [paths])
DEMO_LOGS = [
    ('okafor-rnaseq-timecourse', 'ACTION_FOLDER_CREATED', '', ['raw_reads']),
    ('okafor-rnaseq-timecourse', 'ACTION_FILE_ADDED', '',
     ['raw_reads/S01_L001_R1.fastq.gz', 'raw_reads/S01_L001_R2.fastq.gz']),
    ('okafor-rnaseq-timecourse', 'ACTION_FILE_ADDED', '',
     ['raw_reads/S02_L001_R1.fastq.gz', 'raw_reads/S02_L001_R2.fastq.gz']),
    ('okafor-rnaseq-timecourse', 'ACTION_RSYNC', 'Files rsynced by r.okafor@example.edu',
     ['alignments/']),
    ('okafor-rnaseq-timecourse', 'ACTION_PERMISSIONS_UPDATED',
     'Permissions updated for Okafor Lab', []),
    ('okafor-rnaseq-timecourse', 'ACTION_RENAMED', 'multiqc.html renamed to multiqc_report.html',
     ['qc_reports/multiqc_report.html']),
    ('okafor-rnaseq-timecourse', 'ACTION_USER_EMAILED',
     'Emailed participants: the time course data is ready to download.', []),
    ('novaseq-240311-delivery', 'ACTION_FILE_ADDED', '',
     ['fastq/SampleA_S1_R1.fastq.gz', 'fastq/SampleA_S1_R2.fastq.gz']),
    ('novaseq-240311-delivery', 'ACTION_RSYNC', 'Files rsynced by m.lindqvist@example.edu',
     ['fastq/']),
    ('novaseq-240311-delivery', 'ACTION_DELETED', '', ['fastq/SampleC_S3_R1.fastq.gz']),
]


def all_demo_usernames():
    return [u[0] for u in DEMO_USERS]


def all_demo_group_names():
    return [g[0] for g in DEMO_GROUPS]


def all_demo_share_slugs():
    return [s['slug'] for s in DEMO_SHARES]
