// Announce.vue.js
// Singleton off-screen live region (WCAG 4.1.3). Page code calls
// `announce(msg)` from state.js; this component renders the current message
// inside an aria-live region so screen readers read it out without visual
// disruption.
//
// Bootstrap 5 + components.css supply `.announce-region` for sr-only
// positioning.

import { defineComponent } from 'vue';
import { state } from '/static/js/app/state.js';

export const Announce = defineComponent({
    name: 'Announce',
    setup() {
        return { state };
    },
    template: `
        <div
            class="announce-region"
            role="status"
            :aria-live="state.announce.politeness"
            aria-atomic="true"
        >{{ state.announce.message }}</div>
    `,
});
