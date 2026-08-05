// Regenerates every screenshot used in the BioShare user manual.
//
// The 2017 docs went stale largely because their screenshots were captured by
// hand and nobody could tell which ones had rotted. These are generated instead:
// re-run this after any UI change and `git diff docs/images/screenshots/` shows
// exactly which screens moved.
//
// Usage (see README.md in this directory):
//   npm ci && npx playwright install chromium && node capture.js
//
// Environment:
//   BIOSHARE_URL       default http://bioshare:9999
//   BIOSHARE_USER      default test@fake.com
//   BIOSHARE_PASSWORD  default OnlyForTesting1!
//
// Point these at a development instance only. The script logs in and reads
// data; it never writes. It logs in exactly once and reuses the session,
// because the login view is rate limited (10/hour per username and per IP).

const fs = require('fs');
const path = require('path');
const { authenticatedPage, BASE, VIEWPORT } = require('./session');

const OUT = path.resolve(__dirname, '..', '..', 'docs', 'images', 'screenshots');

// Delay between screens. Several BioShare views are rate limited, and a tight
// loop gets later screens served the throttle page instead of content.
const PAUSE_MS = Number(process.env.BIOSHARE_CAPTURE_PAUSE_MS || 2500);

// Viewport is fixed in session.js so re-runs are byte-comparable: 1280x800 suits
// the docs content width and keeps the sidebar visible (below ~992px Bootstrap
// stacks it).

// Screens to capture. `prepare` runs after navigation and before the shot, for
// screens that need a click to reach. `clip` limits the shot to one element.
// Adding a screen should be a one-line change here.
const SCREENS = [
    {
        name: 'home',
        url: () => '/',
        waitFor: 'table',
    },
    {
        name: 'share-files',
        url: (ctx) => `/bioshare/view/${ctx.shareId}/`,
        waitFor: 'table',
    },
    {
        name: 'share-search',
        url: (ctx) => `/bioshare/view/${ctx.shareId}/`,
        waitFor: 'table',
        prepare: async (page) => clickTab(page, 'Search'),
    },
    {
        name: 'share-logs',
        url: (ctx) => `/bioshare/view/${ctx.shareId}/`,
        waitFor: 'table',
        prepare: async (page) => clickTab(page, 'Logs'),
    },
    {
        name: 'download-options',
        url: (ctx) => `/bioshare/view/${ctx.shareId}/`,
        waitFor: 'table',
        prepare: async (page) => openMenu(page, 'Download'),
    },
    {
        name: 'upload-options',
        url: (ctx) => `/bioshare/view/${ctx.shareId}/`,
        waitFor: 'table',
        prepare: async (page) => openMenu(page, 'Upload'),
    },
    {
        name: 'permissions',
        url: (ctx) => `/bioshare/permissions/${ctx.shareId}/`,
        waitFor: 'table, form',
    },
    {
        name: 'create-share',
        url: () => '/bioshare/create/',
        waitFor: 'form',
    },
    {
        name: 'groups',
        url: () => '/bioshare/groups/',
        waitFor: 'table, h1, h2',
    },
    {
        name: 'ssh-keys',
        url: () => '/bioshare/ssh_keys/list/',
        waitFor: 'table, h1, h2',
    },
];

async function clickTab(page, label) {
    const tab = page.getByRole('tab', { name: label });
    if (await tab.count()) {
        await tab.first().click();
        await page.waitForTimeout(600);
    }
}

async function openMenu(page, label) {
    const button = page.getByRole('button', { name: label });
    if (await button.count()) {
        await button.first().click();
        await page.waitForTimeout(400);
    }
}

// Vue mounts asynchronously and several tables load over the API, so a bare
// networkidle is not enough on its own -- wait for real content too.
async function settle(page, waitFor) {
    await page.waitForLoadState('networkidle').catch(() => {});
    if (waitFor) {
        await page.waitForSelector(waitFor, { timeout: 15000 }).catch(() => {});
    }
    await page.waitForTimeout(500);
}

// Pages BioShare serves that must never end up in the manual. Without this check
// a throttled or errored response is screenshotted and committed like any other
// page -- silently, which is precisely the rot this pipeline exists to avoid.
const BAD_PAGE_MARKERS = [
    'your request has been throttled',
    'Unable to locate the files',
    "You don't have permission",
    'Page not found',
    'Server error',
];

async function assertRealPage(page, name) {
    const body = await page.innerText('body').catch(() => '');
    const hit = BAD_PAGE_MARKERS.find((m) => body.toLowerCase().includes(m.toLowerCase()));
    if (hit) {
        throw new Error(
            `page shows "${hit}" instead of content` +
            (/throttl/i.test(hit)
                ? ' -- the instance is rate limiting; wait a few minutes and re-run'
                : '')
        );
    }
    if (body.trim().length < 200) {
        throw new Error(`page looks empty (${body.trim().length} chars of text)`);
    }
}

// Read a share id off the home page rather than hard-coding one, so the script
// keeps working against any dev database.
//
// Candidates are checked rather than taking the first link: a share whose backing
// directory has gone missing renders "Unable to locate the files" instead of a
// file table, and screenshotting that error page is worse than no screenshot.
// Prefer the share with the most rows so the file table isn't nearly empty.
async function discoverShareId(page) {
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
    await settle(page, 'table');

    const hrefs = await page.$$eval('a[href*="/bioshare/view/"]', (as) => [
        ...new Set(as.map((a) => a.getAttribute('href'))),
    ]);
    if (!hrefs.length) {
        throw new Error(
            'No shares found on the home page. Create at least one share on the ' +
            'target instance before capturing screenshots.'
        );
    }

    let best = null;
    for (const href of hrefs) {
        const id = (href.match(/\/bioshare\/view\/([^/]+)\//) || [])[1];
        if (!id) continue;
        await page.goto(BASE + href, { waitUntil: 'networkidle' });
        await settle(page, 'table');
        const body = await page.innerText('body').catch(() => '');
        if (body.includes('Unable to locate the files')) continue;
        const rows = await page.$$eval('table tbody tr', (r) => r.length).catch(() => 0);
        if (!best || rows > best.rows) best = { id, rows };
    }

    if (!best) {
        throw new Error(
            `None of the ${hrefs.length} share(s) on this instance render a file ` +
            'listing -- their backing directories are missing. Fix or seed the data ' +
            'before capturing screenshots.'
        );
    }
    return best.id;
}

(async () => {
    fs.mkdirSync(OUT, { recursive: true });

    // Two visual normalisations, applied as CSS so nothing in the database changes:
    //  - animations and the text caret would otherwise make two runs differ;
    //  - site announcements are instance-specific and outside the manual's scope,
    //    and on a busy instance they push the actual page content below the fold.
    const { browser, page, reused } = await authenticatedPage({
        viewport: VIEWPORT,
        init: (context) =>
            context.addInitScript(() => {
                const style = document.createElement('style');
                style.textContent =
                    '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' +
                    '#message-list-mount{display:none!important}';
                document.addEventListener('DOMContentLoaded', () =>
                    document.head.appendChild(style)
                );
            }),
    });
    console.log(reused ? 'Reusing cached session\n' : 'Logged in, session cached\n');

    const failures = [];

    try {
        const ctx = { shareId: await discoverShareId(page) };
        console.log(`Using share ${ctx.shareId}\n`);

        for (const screen of SCREENS) {
            const url = BASE + screen.url(ctx);
            try {
                await page.goto(url, { waitUntil: 'domcontentloaded' });
                await settle(page, screen.waitFor);
                await assertRealPage(page, screen.name);
                if (screen.prepare) await screen.prepare(page);
                await assertRealPage(page, screen.name);

                const file = path.join(OUT, `${screen.name}.png`);
                await page.screenshot({ path: file, scale: 'css' });
                console.log(`  ✓ ${screen.name}.png`);
                // Be gentle: several views are rate limited, and hammering them
                // gets later screens replaced by the throttle page.
                await page.waitForTimeout(PAUSE_MS);
            } catch (err) {
                failures.push(`${screen.name}: ${err.message}`);
                console.log(`  ✗ ${screen.name} — ${err.message}`);
            }
        }
    } finally {
        await browser.close();
    }

    if (failures.length) {
        console.error(`\n${failures.length} screen(s) failed:`);
        failures.forEach((f) => console.error(`  - ${f}`));
        process.exit(1);
    }
    console.log(`\nWrote ${SCREENS.length} screenshots to ${OUT}`);
})();
