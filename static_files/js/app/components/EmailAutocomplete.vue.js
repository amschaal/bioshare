// EmailAutocomplete.vue.js
// Recipient picker for the permissions page. Wraps the generic Combobox
// primitive against /bioshare/api/get_addresses/ so an admin can pick a known
// email or group — and, because adding *new* users by email is the whole
// point, also offers an "Add <typed value>" option for arbitrary input that
// isn't in the address book yet.
//
// Replaces the jquery-textcomplete autocomplete on the #addUser textarea in
// templates/share/permissions.html.
//
// Endpoint:
//   GET /bioshare/api/get_addresses/?q=<text>
//   -> { emails: [string], groups: [string] }
//
// Emits:
//   add(query)  - the chosen recipient, ready to hand to the share_with API.
//                 Groups are emitted prefixed with "group:" since that is how
//                 share_with parses them.

import { defineComponent } from 'vue';
import { apiGet } from '/static/js/app/api.js';
import { Combobox } from '/static/js/app/components/Combobox.vue.js';

const looksLikeEmail = (s) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s);

export const EmailAutocomplete = defineComponent({
    name: 'EmailAutocomplete',
    components: { Combobox },
    props: {
        inputId: { type: String, default: null },
        placeholder: { type: String, default: 'Add a user by email or a group' },
    },
    emits: ['add'],
    setup(props, { emit }) {
        async function fetchFn(query) {
            const term = (query || '').trim();
            let emails = [];
            let groups = [];
            try {
                const r = await apiGet('/bioshare/api/get_addresses/', term ? { q: term } : undefined);
                emails = r?.emails || [];
                groups = r?.groups || [];
            } catch (e) {
                // Network/permission failure — fall through to just the typed value.
            }

            const lower = term.toLowerCase();
            const items = [];

            // Let the admin commit an arbitrary email that isn't in the book yet.
            if (term && looksLikeEmail(term) && !emails.some(e => e.toLowerCase() === lower)) {
                items.push({ key: 'custom:' + term, label: `Add "${term}"`, value: term });
            }
            for (const e of emails) {
                if (!term || e.toLowerCase().includes(lower)) {
                    items.push({ key: 'email:' + e, label: e, value: e });
                }
            }
            for (const g of groups) {
                if (!term || g.toLowerCase().includes(lower)) {
                    items.push({ key: 'group:' + g, label: `Group: ${g}`, value: 'group:' + g });
                }
            }
            return items;
        }

        function onSelect(item) {
            if (item?.value) emit('add', item.value);
        }

        return { fetchFn, onSelect };
    },
    template: `
        <Combobox
            :fetch-fn="fetchFn"
            :input-id="inputId"
            :placeholder="placeholder"
            item-key="key"
            item-label="label"
            empty-text="Type a full email address to add a new user"
            @select="onSelect"
        />
    `,
});
