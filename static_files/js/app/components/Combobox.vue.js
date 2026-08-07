// Combobox.vue.js
// Async-fetching combobox built on Reka UI Combobox parts. The caller passes
// a fetchFn(query: string) => Promise<item[]>. We debounce input, manage
// loading/items state, and pass `ignore-filter` so Reka UI doesn't filter
// locally (server already filtered).
//
// Item shape (default):  { value: string|number|object, label: string }
// Customize with :item-key, :item-label props if your shape differs.
//
// WAI-ARIA pattern: combobox + listbox.

import { defineComponent, ref, watch, onUnmounted } from 'vue';
import {
    ComboboxRoot, ComboboxAnchor, ComboboxInput, ComboboxTrigger,
    ComboboxPortal, ComboboxContent, ComboboxViewport,
    ComboboxItem, ComboboxEmpty,
} from 'reka-ui';

export const Combobox = defineComponent({
    name: 'Combobox',
    components: {
        ComboboxRoot, ComboboxAnchor, ComboboxInput, ComboboxTrigger,
        ComboboxPortal, ComboboxContent, ComboboxViewport, ComboboxItem, ComboboxEmpty,
    },
    props: {
        modelValue: { type: [String, Number, Object, Array], default: null },
        fetchFn: { type: Function, required: true },         // async (query) => item[]
        inputId: { type: String, default: null },            // id for the <input>, so an external <label for> can target it
        placeholder: { type: String, default: 'Search...' },
        multiple: { type: Boolean, default: false },
        debounceMs: { type: Number, default: 250 },
        itemKey: { type: String, default: 'value' },
        itemLabel: { type: String, default: 'label' },
        emptyText: { type: String, default: 'No results' },
    },
    emits: ['update:modelValue', 'select'],
    setup(props, { emit }) {
        const items = ref([]);
        const searchTerm = ref('');
        const loading = ref(false);
        let timer = null;

        async function doFetch(q) {
            loading.value = true;
            try {
                const result = await props.fetchFn(q);
                items.value = Array.isArray(result) ? result : [];
            } catch (e) {
                items.value = [];
            } finally {
                loading.value = false;
            }
        }

        watch(searchTerm, q => {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => doFetch(q), props.debounceMs);
        });

        // Initial empty-query fetch so the listbox isn't empty on first focus.
        doFetch('');

        onUnmounted(() => { if (timer) clearTimeout(timer); });

        const labelOf = (item) => {
            if (item == null) return '';
            return typeof item === 'object' ? item[props.itemLabel] : String(item);
        };
        const keyOf = (item, idx) => {
            if (item == null) return idx;
            return typeof item === 'object' ? item[props.itemKey] : item;
        };

        function onSelect(item) {
            emit('update:modelValue', item);
            emit('select', item);
        }

        return { items, searchTerm, loading, labelOf, keyOf, onSelect };
    },
    template: `
        <combobox-root
            :model-value="modelValue"
            :multiple="multiple"
            :ignore-filter="true"
            @update:model-value="onSelect"
        >
            <combobox-anchor class="position-relative">
                <combobox-input
                    v-model="searchTerm"
                    :id="inputId || undefined"
                    :placeholder="placeholder"
                    class="form-control"
                    :aria-busy="loading || undefined"
                />
                <combobox-trigger
                    class="btn btn-sm btn-link position-absolute end-0 top-50 translate-middle-y"
                    aria-label="Toggle options"
                    style="pointer-events: auto;"
                >
                    <span class="bi bi-chevron-down" aria-hidden="true"></span>
                </combobox-trigger>
            </combobox-anchor>
            <combobox-portal>
                <combobox-content
                    class="bg-white rounded-2 shadow border"
                    style="z-index: 1080; min-width: 16rem;"
                    position="popper"
                    side="bottom"
                    :side-offset="4"
                    align="start"
                >
                    <combobox-viewport class="overflow-auto" style="max-height: 18rem;">
                        <combobox-item
                            v-for="(item, idx) in items"
                            :key="keyOf(item, idx)"
                            :value="item"
                            class="px-3 py-2 cursor-pointer"
                            style="user-select: none;"
                        >{{ labelOf(item) }}</combobox-item>
                        <combobox-empty class="px-3 py-2 text-muted small">{{ emptyText }}</combobox-empty>
                    </combobox-viewport>
                </combobox-content>
            </combobox-portal>
        </combobox-root>
    `,
});
