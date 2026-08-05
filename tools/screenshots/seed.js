// Creates the demo content that the manual's screenshots show.
//
// Run this once against a development instance before `capture.js`, so the file
// listing screenshots show a realistic share instead of "This share is empty".
//
//   node seed.js
//
// It works through the web UI rather than the ORM, so it needs no database
// access and exercises the same paths a real user would. It is idempotent:
// re-running finds the existing demo share by name and tops up anything missing,
// rather than creating duplicates.
//
// Development instances only. It creates a share and uploads files.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { authenticatedPage, BASE } = require('./session');

const SHARE_NAME = 'Example RNA-seq dataset';
const SHARE_DESCRIPTION =
    'Paired-end RNA-seq for the demo project, plus alignments and QC reports. ' +
    'Example data used in the BioShare user guide.';
// The tags field validates as comma-delimited alphanumeric -- hyphens are
// rejected, so no "rna-seq" here.
const SHARE_TAGS = 'rnaseq, transcriptome, demo';

const FOLDERS = ['raw_reads', 'alignments', 'qc_reports'];

// Small placeholder files -- enough to make a realistic listing with a spread of
// extensions and sizes. README.md is deliberately included: BioShare renders it
// below the file table, and the manual documents that.
const FILES = {
    'README.md': `# Example RNA-seq dataset

This share holds the demo dataset used in the BioShare user guide.

## Layout

| Folder | Contents |
|---|---|
| \`raw_reads\` | Paired-end FASTQ files as delivered by the sequencer |
| \`alignments\` | Coordinate-sorted BAM files and their indexes |
| \`qc_reports\` | Per-sample quality control reports |

## Notes

Any \`README.md\` placed at the top of a share is rendered here automatically,
which is a convenient place to describe how the data is organised.
`,
    'samples.csv': [
        'sample_id,condition,replicate,read_pairs',
        'S01,control,1,24183991',
        'S02,control,2,23874120',
        'S03,treated,1,25017433',
        'S04,treated,2,24662087',
        '',
    ].join('\n'),
    'checksums.txt': [
        'd41d8cd98f00b204e9800998ecf8427e  raw_reads/S01_R1.fastq.gz',
        'c157a79031e1c40f85931829bc5fc552  raw_reads/S01_R2.fastq.gz',
        '9f2feb0f21b8dbd4d6a4a1b1b1e0a4f5  alignments/S01.bam',
        '',
    ].join('\n'),
};

const log = (msg) => console.log(msg);

async function findShare(page) {
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
    await page.waitForSelector('table', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);
    const link = page.locator(`a[href*="/bioshare/view/"]`, { hasText: SHARE_NAME });
    if (!(await link.count())) return null;
    const href = await link.first().getAttribute('href');
    return (href.match(/\/bioshare\/view\/([^/]+)\//) || [])[1] || null;
}

async function createShare(page) {
    await page.goto(`${BASE}/bioshare/create/`, { waitUntil: 'networkidle' });
    // Target the crispy-form field ids directly. Label text carries a required
    // marker ("Name*") and the sidebar has its own share-name box, so id
    // selectors are the unambiguous choice here.
    await page.locator('#id_name').fill(SHARE_NAME);
    await page.locator('#id_notes').fill(SHARE_DESCRIPTION);
    await page.locator('#id_tags').fill(SHARE_TAGS);

    // Filesystem is required and defaults to the blank "---------" choice, so it
    // has to be set explicitly. Pick the first real option rather than a fixed
    // pk, since that differs per instance.
    const fsValue = await page.$eval(
        '#id_filesystem',
        (sel) => Array.from(sel.options).map((o) => o.value).filter(Boolean)[0]
    );
    if (!fsValue) {
        throw new Error(
            'No Filesystem is configured on this instance. Add one in the Django ' +
            'admin (see README) before seeding.'
        );
    }
    await page.selectOption('#id_filesystem', fsValue);

    await page.getByRole('button', { name: /create share/i }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1200);
    const match = page.url().match(/\/bioshare\/view\/([^/]+)\//);
    if (!match) {
        const errors = await page
            .$$eval('.invalid-feedback, .errorlist, .alert-danger', (es) =>
                es.map((e) => e.textContent.trim()).filter(Boolean)
            )
            .catch(() => []);
        throw new Error(
            `Share creation did not land on a share page (at ${page.url()})` +
            (errors.length ? `\nForm errors: ${errors.join(' | ')}` : '')
        );
    }
    return match[1];
}

async function listing(page) {
    return (await page.innerText('table').catch(() => '')) || '';
}

async function createFolder(page, name) {
    if ((await listing(page)).includes(name)) {
        log(`    = ${name}/ (exists)`);
        return;
    }
    await page.getByRole('button', { name: /new folder/i }).first().click();
    await page.waitForTimeout(600);
    // Scope to the dialog: the page behind it has its own text inputs (column
    // filters, the sidebar share search) that would otherwise match first.
    const dialog = page.getByRole('dialog');
    await dialog.waitFor({ timeout: 10000 });
    await dialog.locator('input[type="text"]:visible, input:not([type]):visible').first().fill(name);
    await dialog.getByRole('button', { name: /^Create$/ }).click();
    await page.waitForTimeout(1500);
    log(`    + ${name}/`);
}

async function uploadFiles(page, dir, names) {
    await page.getByRole('button', { name: /^Upload/ }).first().click();
    await page.waitForTimeout(400);
    await page.getByRole('menuitem', { name: /browser/i }).click();
    await page.waitForTimeout(800);

    // Choosing "Browser" reveals an inline drop box rather than a modal, and the
    // upload starts as soon as files are selected -- there is no confirm button.
    // (Do not go looking for one: a button matcher anchored on "Upload" hits the
    // dropdown trigger and cancels the upload that just started.)
    const input = page.locator('#file-uploader-input');
    await input.waitFor({ state: 'attached', timeout: 10000 });
    await input.setInputFiles(names.map((n) => path.join(dir, n)));

    // Wait for the uploaded names to appear in the listing rather than guessing
    // at a fixed delay.
    const deadline = Date.now() + 60000;
    while (Date.now() < deadline) {
        await page.waitForTimeout(1500);
        const text = await listing(page);
        if (names.every((n) => text.includes(n))) return;
    }
    log('    ! upload did not complete within 60s');
}

(async () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bioshare-seed-'));
    for (const [name, content] of Object.entries(FILES)) {
        fs.writeFileSync(path.join(tmp, name), content);
    }

    const { browser, page } = await authenticatedPage({ viewport: { width: 1280, height: 900 } });

    try {
        let shareId = await findShare(page);
        if (shareId) {
            log(`Reusing existing demo share ${shareId} ("${SHARE_NAME}")`);
        } else {
            shareId = await createShare(page);
            log(`Created demo share ${shareId} ("${SHARE_NAME}")`);
        }

        await page.goto(`${BASE}/bioshare/view/${shareId}/`, { waitUntil: 'networkidle' });
        await page.waitForSelector('table', { timeout: 15000 }).catch(() => {});
        await page.waitForTimeout(800);

        log('  folders:');
        for (const folder of FOLDERS) {
            await createFolder(page, folder);
        }

        const current = await listing(page);
        const missing = Object.keys(FILES).filter((n) => !current.includes(n));
        if (missing.length) {
            log(`  uploading: ${missing.join(', ')}`);
            await uploadFiles(page, tmp, missing);
        } else {
            log('  files: all present');
        }

        await page.reload({ waitUntil: 'networkidle' });
        await page.waitForTimeout(1200);
        const final = await listing(page);
        const present = [...FOLDERS, ...Object.keys(FILES)].filter((n) => final.includes(n));
        log(`\nShare ${shareId} now lists ${present.length}/${FOLDERS.length + Object.keys(FILES).length} expected entries.`);
        if (present.length < FOLDERS.length + Object.keys(FILES).length) {
            log('Missing: ' + [...FOLDERS, ...Object.keys(FILES)].filter((n) => !final.includes(n)).join(', '));
            process.exitCode = 1;
        }
    } finally {
        await browser.close();
        fs.rmSync(tmp, { recursive: true, force: true });
    }
})();
