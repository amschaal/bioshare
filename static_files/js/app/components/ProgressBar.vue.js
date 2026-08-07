// ProgressBar.vue.js
// Accessible progress indicator. role="progressbar" with aria-valuenow/min/max
// so screen readers announce upload (or any) progress.
//
// WAI-ARIA pattern: progressbar.

import { defineComponent, computed } from 'vue';

export const ProgressBar = defineComponent({
    name: 'ProgressBar',
    props: {
        value: { type: Number, required: true },   // 0-100
        label: { type: String, default: 'Progress' },
        variant: { type: String, default: 'primary' }, // bootstrap bg-* variant
        showPercent: { type: Boolean, default: true },
    },
    setup(props) {
        const pct = computed(() => Math.max(0, Math.min(100, Math.round(props.value))));
        return { pct };
    },
    template: `
        <div
            class="progress"
            role="progressbar"
            :aria-label="label"
            :aria-valuenow="pct"
            aria-valuemin="0"
            aria-valuemax="100"
        >
            <div :class="['progress-bar', 'bg-' + variant]" :style="{ width: pct + '%' }">
                <span v-if="showPercent">{{ pct }}%</span>
            </div>
        </div>
    `,
});
