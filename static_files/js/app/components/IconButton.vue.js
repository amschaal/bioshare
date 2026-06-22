// IconButton.vue.js
// Real <button> with an aria-label and a Bootstrap Icons glyph. Replaces every
// <i role="button" tabindex="0"> and <a href="#"> action site-wide so all icon
// actions are keyboard-operable and announced correctly (WCAG 2.1.1, 4.1.2).

import { defineComponent, computed } from '/static/lib/vue/vue.esm-browser.prod.js';

export const IconButton = defineComponent({
    name: 'IconButton',
    props: {
        icon: { type: String, required: true },       // bi-* name, without the 'bi-' prefix
        label: { type: String, required: true },      // accessible name; also used as tooltip
        variant: { type: String, default: 'link' },   // bootstrap btn-* variant
        size: { type: String, default: 'sm' },        // 'sm' | '' | 'lg'
        disabled: { type: Boolean, default: false },
        type: { type: String, default: 'button' },
    },
    emits: ['click'],
    setup(props) {
        const cls = computed(() => [
            'btn',
            props.variant ? `btn-${props.variant}` : '',
            props.size ? `btn-${props.size}` : '',
        ]);
        return { cls };
    },
    template: `
        <button
            :type="type"
            :class="cls"
            :aria-label="label"
            :title="label"
            :disabled="disabled"
            @click="$emit('click', $event)"
        ><span :class="'bi bi-' + icon" aria-hidden="true"></span></button>
    `,
});
