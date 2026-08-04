// state.js — tiny reactive store for cross-component UI state.
//
// Use Vue's reactive() so anything reading from `state` re-renders on change.
// Toast + announce queues are imperative APIs that page code or components
// call without needing to know who's listening.

import { reactive } from 'vue';

const BIOSHARE = (typeof window !== 'undefined' && window.BIOSHARE) || {};

export const state = reactive({
    user: {
        authenticated: !!BIOSHARE.user?.authenticated,
        username: BIOSHARE.user?.username || '',
        isSuperuser: !!BIOSHARE.user?.isSuperuser,
    },
    urls: BIOSHARE.urls || {},
    // ToastHost reads from this list and renders one element per entry.
    toasts: [],
    // Announce singleton reads .message and exposes it inside an aria-live region.
    announce: { message: '', politeness: 'polite' },
    // ConfirmDialog watches this; when non-null it renders. Setting to null closes.
    // Shape: { title, message, confirmLabel, cancelLabel, danger, resolve }
    confirm: null,
});

let _nextToastId = 1;

function pushToast(kind, message, options = {}) {
    const id = _nextToastId++;
    const toast = {
        id,
        kind, // 'info' | 'success' | 'warning' | 'error'
        message,
        timeout: options.timeout ?? (kind === 'error' ? 10000 : 4000),
        createdAt: Date.now(),
    };
    state.toasts.push(toast);
    if (toast.timeout > 0) {
        setTimeout(() => dismissToast(id), toast.timeout);
    }
    return id;
}

export function dismissToast(id) {
    const i = state.toasts.findIndex(t => t.id === id);
    if (i !== -1) state.toasts.splice(i, 1);
}

export const toast = {
    info(msg, opts) { return pushToast('info', msg, opts); },
    success(msg, opts) { return pushToast('success', msg, opts); },
    warning(msg, opts) { return pushToast('warning', msg, opts); },
    error(msg, opts) { return pushToast('error', msg, opts); },
};

/**
 * Show a confirmation dialog (alertdialog). Returns a Promise that resolves
 * to true if the user confirmed, false if they cancelled / dismissed.
 * Pattern:
 *   const ok = await confirm({ title: 'Delete?', message: '...', danger: true });
 *   if (ok) doDelete();
 */
export function confirm(options) {
    return new Promise(resolve => {
        state.confirm = {
            title: options.title || 'Confirm',
            message: options.message || '',
            confirmLabel: options.confirmLabel,
            cancelLabel: options.cancelLabel,
            danger: !!options.danger,
            resolve,
        };
    });
}

/**
 * Push a message into the global aria-live region.
 * `politeness` is 'polite' (default — wait for AT to be idle) or 'assertive'
 * (interrupt). Re-setting to the same string after a tick re-triggers AT.
 */
export function announce(message, politeness = 'polite') {
    state.announce.message = '';
    state.announce.politeness = politeness;
    // Defer so the cleared->set transition fires a re-announcement even when
    // the message text is identical to the previous one.
    setTimeout(() => { state.announce.message = message; }, 30);
}
