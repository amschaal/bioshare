// ShareAutocomplete.vue.js
// Sidebar typeahead for finding shares by name. Wraps the generic Combobox
// primitive against the /bioshare/api/share_autocomplete/ endpoint and
// navigates to the selected share's URL on selection.
//
// Replaces the legacy jQuery bootstrap-typeahead on #share_autocomplete in
// templates/base.html.
//
// Endpoint:
//   GET /bioshare/api/share_autocomplete/?query=<text>
//   -> { status: 'success', shares: [{ id, url, name, notes }] }

import { defineComponent } from 'vue';
import { apiGet } from '/static/js/app/api.js';
import { Combobox } from '/static/js/app/components/Combobox.vue.js';

export const ShareAutocomplete = defineComponent({
    name: 'ShareAutocomplete',
    components: { Combobox },
    props: {
        placeholder: { type: String, default: 'Search by share name' },
    },
    setup() {
        async function fetchFn(query) {
            if (!query || query.length < 1) return [];
            try {
                const r = await apiGet('/bioshare/api/share_autocomplete/', { query });
                return r?.shares || [];
            } catch (e) {
                return [];
            }
        }

        function onSelect(item) {
            if (item?.url) window.location = item.url;
        }

        return { fetchFn, onSelect };
    },
    template: `
        <Combobox
            :fetch-fn="fetchFn"
            :placeholder="placeholder"
            item-key="id"
            item-label="name"
            empty-text="No shares match"
            @select="onSelect"
        />
    `,
});
