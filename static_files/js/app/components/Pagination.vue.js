// Pagination.vue.js
// Accessible page navigation. Renders Prev / Next + a numbered window around
// the current page. Uses <nav aria-label="..."> + <button aria-current="page">
// (WCAG 1.3.1, 2.4.3, 4.1.2).

import { defineComponent, computed } from 'vue';

export const Pagination = defineComponent({
    name: 'Pagination',
    props: {
        page: { type: Number, required: true },
        totalPages: { type: Number, required: true },
        windowSize: { type: Number, default: 5 },
        ariaLabel: { type: String, default: 'Pagination' },
    },
    emits: ['update:page'],
    setup(props) {
        const visiblePages = computed(() => {
            const total = props.totalPages;
            if (total <= 1) return [];
            const w = props.windowSize;
            const half = Math.floor(w / 2);
            let start = Math.max(1, props.page - half);
            let end = Math.min(total, start + w - 1);
            start = Math.max(1, end - w + 1);
            const out = [];
            for (let i = start; i <= end; i++) out.push(i);
            return out;
        });

        const hasPrev = computed(() => props.page > 1);
        const hasNext = computed(() => props.page < props.totalPages);

        return { visiblePages, hasPrev, hasNext };
    },
    template: `
        <nav :aria-label="ariaLabel" v-if="totalPages > 1">
            <ul class="pagination mb-0">
                <li :class="['page-item', { disabled: !hasPrev }]">
                    <button
                        type="button"
                        class="page-link"
                        :disabled="!hasPrev"
                        aria-label="Previous page"
                        @click="$emit('update:page', page - 1)"
                    ><span aria-hidden="true">&laquo;</span></button>
                </li>
                <li
                    v-for="p in visiblePages"
                    :key="p"
                    :class="['page-item', { active: p === page }]"
                >
                    <button
                        type="button"
                        class="page-link"
                        :aria-current="p === page ? 'page' : undefined"
                        :aria-label="'Page ' + p"
                        @click="$emit('update:page', p)"
                    >{{ p }}</button>
                </li>
                <li :class="['page-item', { disabled: !hasNext }]">
                    <button
                        type="button"
                        class="page-link"
                        :disabled="!hasNext"
                        aria-label="Next page"
                        @click="$emit('update:page', page + 1)"
                    ><span aria-hidden="true">&raquo;</span></button>
                </li>
            </ul>
        </nav>
    `,
});
