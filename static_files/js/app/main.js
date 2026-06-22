// main.js — global Vue app bootstrap. Mounts singleton components
// (ToastHost, Announce, ConfirmDialog) and exposes their imperative APIs
// to non-Vue callers via window.BIOSHARE.
//
// Loaded by base.html as a single <script type="module">. Page-specific
// orchestrators in pages/*.js are loaded independently (also as modules)
// and run alongside this app, mounting their own Vue instances onto
// page-specific DOM roots.

import { createApp, h } from 'vue';
import { state, toast, announce, confirm as openConfirm, dismissToast } from '/static/js/app/state.js';
import { ToastHost } from '/static/js/app/components/ToastHost.vue.js';
import { Announce } from '/static/js/app/components/Announce.vue.js';
import { ConfirmDialog } from '/static/js/app/components/ConfirmDialog.vue.js';

const app = createApp({
    render() {
        return [h(Announce), h(ToastHost), h(ConfirmDialog)];
    },
});

// Singletons mount onto #bioshare-globals (added by base.html). All three
// components position themselves via fixed/sr-only so the host node has no
// visual footprint.
const hostId = 'bioshare-globals';
let host = document.getElementById(hostId);
if (!host) {
    host = document.createElement('div');
    host.id = hostId;
    document.body.appendChild(host);
}
app.mount(host);

// Expose imperative APIs for legacy (non-Vue) code that still wants to
// fire a toast or open a confirm dialog during the migration.
window.BIOSHARE = window.BIOSHARE || {};
Object.assign(window.BIOSHARE, {
    state,
    toast,
    confirm: openConfirm,
    announce,
    dismissToast,
});
