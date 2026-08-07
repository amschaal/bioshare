// Shared authenticated-session handling for the docs scripts.
//
// The login view is rate limited to 10 attempts per hour, per username *and* per
// IP. A script that logs in on every run burns that budget fast and then locks
// itself out for an hour, so the session is cached to disk and reused: a normal
// run performs zero logins.
//
// auth.json holds a live session cookie. It is gitignored -- never commit it.

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const BASE = (process.env.BIOSHARE_URL || 'http://bioshare:9999').replace(/\/$/, '');
const USER = process.env.BIOSHARE_USER || 'test@fake.com';
const PASSWORD = process.env.BIOSHARE_PASSWORD || 'OnlyForTesting1!';
const AUTH_FILE = path.resolve(__dirname, 'auth.json');

const VIEWPORT = { width: 1280, height: 800 };

async function isAuthenticated(page) {
    await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
    return !page.url().includes('/accounts/login');
}

async function logIn(page) {
    await page.goto(`${BASE}/accounts/login/`, { waitUntil: 'networkidle' });
    await page.getByRole('textbox', { name: /email/i }).fill(USER);
    await page.getByRole('textbox', { name: /password/i }).fill(PASSWORD);
    await page.getByRole('button', { name: /log in/i }).click();
    await page.waitForLoadState('networkidle');
    if (page.url().includes('/accounts/login')) {
        throw new Error(
            'Login failed. Either the credentials are wrong, or the rate limit ' +
            '(10 attempts/hour per username and per IP) has been tripped -- in ' +
            'which case wait an hour, or reuse an existing auth.json.'
        );
    }
}

/**
 * Open a browser with an authenticated page, reusing a cached session when one
 * is still valid. Returns { browser, context, page } -- caller closes browser.
 *
 * @param {object} opts
 * @param {object} [opts.viewport]
 * @param {(context) => Promise<void>} [opts.init] extra context setup (init scripts)
 */
async function authenticatedPage(opts = {}) {
    const viewport = opts.viewport || VIEWPORT;
    const browser = await chromium.launch();

    const makeContext = async (storageState) => {
        const context = await browser.newContext({
            viewport,
            deviceScaleFactor: 1,
            colorScheme: 'light',
            reducedMotion: 'reduce',
            ...(storageState ? { storageState } : {}),
        });
        if (opts.init) await opts.init(context);
        return context;
    };

    if (fs.existsSync(AUTH_FILE)) {
        const context = await makeContext(AUTH_FILE);
        const page = await context.newPage();
        if (await isAuthenticated(page)) {
            return { browser, context, page, reused: true };
        }
        await context.close();
    }

    const context = await makeContext(null);
    const page = await context.newPage();
    await logIn(page);
    await context.storageState({ path: AUTH_FILE });
    return { browser, context, page, reused: false };
}

module.exports = { authenticatedPage, BASE, VIEWPORT, AUTH_FILE };
