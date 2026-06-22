// base.js — orchestrator for the chrome that every page extending base.html
// shares. Mounts:
//   - Sidebar ShareAutocomplete
//   - Top-of-page MessageList (active messages only)
//   - Navbar Shares + Account dropdown menus
//
// Globals (Announce, ToastHost, ConfirmDialog) are mounted by main.js.
//
// Each mount is its own tiny Vue app. Mounting onto a non-existent node is
// a no-op (some pages may omit a mount, e.g. anonymous pages without the
// authenticated sidebar).

import { createApp } from 'vue';
import { ShareAutocomplete } from '/static/js/app/components/ShareAutocomplete.vue.js';
import { MessageList } from '/static/js/app/components/MessageList.vue.js';
import { DropdownMenu, DropdownMenuItem, DropdownMenuSeparator } from '/static/js/app/components/DropdownMenu.vue.js';

const BIOSHARE = window.BIOSHARE || {};

function mountIfPresent(selector, factory) {
    const el = document.querySelector(selector);
    if (!el) return;
    factory().mount(el);
}

// Sidebar share search
mountIfPresent('#share-autocomplete-mount', () => createApp({
    components: { ShareAutocomplete },
    template: `<ShareAutocomplete placeholder="Search by share name" />`,
}));

// Active system messages (top of every authenticated page)
mountIfPresent('#message-list-mount', () => createApp({
    components: { MessageList },
    template: `<MessageList :active="true" />`,
}));

// Navbar dropdown: Shares
mountIfPresent('#nav-shares-dropdown-mount', () => createApp({
    components: { DropdownMenu, DropdownMenuItem },
    setup() {
        const urls = BIOSHARE.urls || {};
        function go(url) { if (url) window.location = url; }
        return { urls, go };
    },
    template: `
        <DropdownMenu label="Shares" variant="outline-light">
            <DropdownMenuItem @select="go(urls.listShares)">List shares</DropdownMenuItem>
            <DropdownMenuItem @select="go(urls.createShare)">Create share</DropdownMenuItem>
        </DropdownMenu>
    `,
}));

// Navbar dropdown: Account
mountIfPresent('#nav-account-dropdown-mount', () => createApp({
    components: { DropdownMenu, DropdownMenuItem },
    setup() {
        const urls = BIOSHARE.urls || {};
        function go(url) { if (url) window.location = url; }
        return { urls, go };
    },
    template: `
        <DropdownMenu label="Account" variant="outline-light">
            <DropdownMenuItem @select="go(urls.passwordChange)">Update Password</DropdownMenuItem>
            <DropdownMenuItem @select="go(urls.sshKeys)">SSH Keys</DropdownMenuItem>
            <DropdownMenuItem @select="go(urls.viewMessages)">System Messages</DropdownMenuItem>
        </DropdownMenu>
    `,
}));
