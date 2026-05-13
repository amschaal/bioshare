// main.js — global Vue app bootstrap. Mounts singleton components
// (ToastHost, Announce, ConfirmDialog) and exposes their imperative APIs
// to non-Vue callers via window.BIOSHARE.
//
// Loaded by base.html as a single <script type="module">. Page-specific
// orchestrators in pages/*.js are loaded independently (also as modules)
// and run alongside this app, mounting their own Vue instances onto
// page-specific DOM roots.

import { createApp, h } from '/static/lib/vue/vue.esm-browser.prod.js';
import { state, toast, announce, dismissToast } from '/static/js/app/state.js';
import { ToastHost } from '/static/js/app/components/ToastHost.vue.js';
import { Announce } from '/static/js/app/components/Announce.vue.js';
import { ConfirmDialogHost } from '/static/js/app/components/ConfirmDialogHost.vue.js';

const app = createApp({
    render() {
        return [h(ToastHost), h(Announce), h(ConfirmDialogHost)];
    },
});

// Singletons mount onto a single host div added to base.html. Components
// inside use position: fixed / sr-only so the host node itself is empty.
const hostId = 'bioshare-globals';
let host = document.getElementById(hostId);
if (!host) {
    host = document.createElement('div');
    host.id = hostId;
    document.body.appendChild(host);
}
app.mount(host);

// Expose imperative APIs for templates that aren't yet Vue-mounted.
window.BIOSHARE = window.BIOSHARE || {};
Object.assign(window.BIOSHARE, {
    state,
    toast,
    dismissToast,
    announce,
});
