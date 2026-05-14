// api.js — fetch wrapper for the BioShareX REST API.
//
// Centralizes CSRF token injection, JSON serialization, error routing
// (401 -> login redirect, 429 -> toast, 5xx -> toast), and the {failed, ...}
// envelope handling used by many endpoints. Replaces csrf.js + lib.js +
// BC.ajax / BC.ajax_form_submit from the legacy stack.

import { toast } from '/static/js/app/state.js';

const BIOSHARE = (typeof window !== 'undefined' && window.BIOSHARE) || {};

function csrfToken() {
    if (BIOSHARE.csrfToken) return BIOSHARE.csrfToken;
    // Cookie fallback for pages where the template didn't render the token.
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
}

function buildUrl(url, params) {
    if (!params) return url;
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v === undefined || v === null) continue;
        if (Array.isArray(v)) {
            for (const item of v) usp.append(k, item);
        } else {
            usp.append(k, v);
        }
    }
    const qs = usp.toString();
    if (!qs) return url;
    return url + (url.includes('?') ? '&' : '?') + qs;
}

async function handleResponse(response, opts = {}) {
    // Auth gate — 401 / unauthenticated body means session expired.
    if (response.status === 401) {
        const loginUrl = BIOSHARE.urls?.login || '/accounts/login/';
        window.location = `${loginUrl}?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
        // Throw so callers' .then() doesn't proceed.
        throw new Error('Not authenticated');
    }

    if (response.status === 429) {
        toast.error('Rate limit exceeded — please slow down and try again.');
        throw new Error('Rate limited');
    }

    if (response.status >= 500) {
        if (!opts.suppressServerErrorToast) {
            toast.error(`Server error (${response.status}). The team has been notified.`);
        }
        throw new Error(`Server error ${response.status}`);
    }

    const isJson = (response.headers.get('content-type') || '').includes('application/json');
    let body = null;
    if (isJson) {
        body = await response.json();
    } else if (response.status !== 204) {
        body = await response.text();
    }

    if (!response.ok) {
        const message = extractErrorMessage(body, response.status);
        if (!opts.suppressErrorToast) toast.error(message);
        const err = new Error(message);
        err.response = response;
        err.body = body;
        throw err;
    }

    return body;
}

// Pull the most useful human-readable message out of a non-2xx JSON body.
// Handles DRF's { detail }, this app's json_error { status, errors: [...] }
// (where errors entries may themselves be Django ErrorList arrays, so we
// flatten), and the occasional { error } singular.
function extractErrorMessage(body, status) {
    if (body && typeof body === 'object') {
        if (body.detail) return String(body.detail);
        if (body.error) return String(body.error);
        if (Array.isArray(body.errors)) {
            const flat = body.errors.flat(Infinity).map(x => String(x)).filter(Boolean);
            if (flat.length) return flat.join(' ');
        }
    }
    if (typeof body === 'string' && body.trim()) return body.trim().slice(0, 300);
    return `Request failed (${status})`;
}

export async function apiGet(url, params, opts) {
    const response = await fetch(buildUrl(url, params), {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
    });
    return handleResponse(response, opts);
}

/**
 * POST with a JSON body. Sets X-CSRFToken from the template-rendered value.
 */
export async function apiPost(url, body, opts = {}) {
    const init = {
        method: opts.method || 'POST',
        credentials: 'same-origin',
        headers: {
            'Accept': 'application/json',
            'X-CSRFToken': csrfToken(),
        },
    };
    if (body instanceof FormData) {
        init.body = body;
    } else if (body !== undefined) {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    }
    const response = await fetch(url, init);
    return handleResponse(response, opts);
}

export const apiPut = (url, body, opts) => apiPost(url, body, { ...opts, method: 'PUT' });
export const apiPatch = (url, body, opts) => apiPost(url, body, { ...opts, method: 'PATCH' });
export const apiDelete = (url, opts) => apiPost(url, undefined, { ...opts, method: 'DELETE' });
