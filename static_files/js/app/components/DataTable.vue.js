// DataTable.vue.js
// Server-side paginated table with sort, filter, column visibility, URL-state
// persistence, and an aria-live announcement on every refresh. Replaces the
// 4 ng-table instances in the legacy app (shares list, logs, groups list,
// group users) plus the DataTables jQuery instance on the file browser.
//
// Props:
//   endpoint       - DRF list URL returning { count, results, next, previous }
//   columns        - [{ key, label, sortable, filterable, filterParam, format, visible }]
//                      filterParam   override URL key for filter (default: col.key)
//                      format(value, item)   return display text/HTML for cell
//                      visible       initial visibility (default true)
//   pageSize       - rows per page (default 10)
//   urlStateKey    - if set, persists {page, ordering, filters} to ?<key>.*
//                      so bookmarks survive page reload. Mirrors LocationSearchState.
//   ariaLabel      - <table aria-label="">; also used for pagination label
//   emptyText      - shown in tbody when results are empty
//
// Slots:
//   cell-<colkey>  - custom cell renderer; receives { item, value } props
//
// WAI-ARIA: <table> + aria-sort on <th> + role="status" announce on refresh.

import { defineComponent, ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { apiGet } from '/static/js/app/api.js';
import { Pagination } from '/static/js/app/components/Pagination.vue.js';
import { announce } from '/static/js/app/state.js';
import { getUrlState, setUrlState } from '/static/js/app/url-state.js';

const FILTER_DEBOUNCE_MS = 400;

export const DataTable = defineComponent({
    name: 'DataTable',
    components: { Pagination },
    props: {
        endpoint: { type: String, required: true },
        columns: { type: Array, required: true },
        pageSize: { type: Number, default: 10 },
        urlStateKey: { type: String, default: '' },
        ariaLabel: { type: String, default: 'Data table' },
        emptyText: { type: String, default: 'No results' },
    },
    setup(props) {
        // Initialize from URL state if a key is provided
        function readUrl() {
            if (!props.urlStateKey) return {};
            return getUrlState()[props.urlStateKey] || {};
        }
        const initial = readUrl();

        const items = ref([]);
        const total = ref(0);
        const page = ref(parseInt(initial.page, 10) || 1);
        const ordering = ref(initial.ordering || null);
        const filters = ref({ ...(initial.filters || {}) });
        const visibility = ref(Object.fromEntries(
            props.columns.map(c => [c.key, initial.visibility?.[c.key] ?? (c.visible !== false)])
        ));
        const loading = ref(false);
        const error = ref(null);

        const totalPages = computed(() => Math.max(1, Math.ceil(total.value / props.pageSize)));
        const visibleColumns = computed(() => props.columns.filter(c => visibility.value[c.key]));

        function writeUrl() {
            if (!props.urlStateKey) return;
            const current = getUrlState();
            setUrlState({
                ...current,
                [props.urlStateKey]: {
                    page: page.value,
                    ordering: ordering.value || undefined,
                    filters: Object.fromEntries(
                        Object.entries(filters.value).filter(([, v]) => v)
                    ),
                    visibility: visibility.value,
                },
            });
        }

        async function fetchPage() {
            loading.value = true;
            error.value = null;
            try {
                const params = { page: page.value, page_size: props.pageSize };
                if (ordering.value) params.ordering = ordering.value;
                for (const col of props.columns) {
                    const v = filters.value[col.key];
                    if (v != null && v !== '') {
                        const paramKey = col.filterParam || col.key;
                        params[paramKey] = v;
                    }
                }
                const r = await apiGet(props.endpoint, params);
                items.value = r.results || [];
                total.value = r.count || 0;
                announce(`${ariaLabel.value || 'Table'}: ${items.value.length} of ${total.value} results`, 'polite');
            } catch (e) {
                error.value = e?.body?.detail || String(e?.message || e);
                items.value = [];
                total.value = 0;
            } finally {
                loading.value = false;
            }
        }
        const ariaLabel = computed(() => props.ariaLabel);

        function changeSort(key) {
            // Tri-state: asc → desc → none
            if (ordering.value === key) ordering.value = '-' + key;
            else if (ordering.value === '-' + key) ordering.value = null;
            else ordering.value = key;
            page.value = 1;
            writeUrl();
            fetchPage();
        }

        function ariaSortFor(key) {
            if (ordering.value === key) return 'ascending';
            if (ordering.value === '-' + key) return 'descending';
            return 'none';
        }

        // Debounced filter input
        let filterTimer = null;
        function onFilterInput(key, value) {
            filters.value[key] = value;
            if (filterTimer) clearTimeout(filterTimer);
            filterTimer = setTimeout(() => {
                page.value = 1;
                writeUrl();
                fetchPage();
            }, FILTER_DEBOUNCE_MS);
        }
        onUnmounted(() => { if (filterTimer) clearTimeout(filterTimer); });

        function gotoPage(p) {
            page.value = p;
            writeUrl();
            fetchPage();
        }

        function toggleColumns(updatedCols) {
            // Called by ColumnPicker when user toggles a checkbox.
            visibility.value = Object.fromEntries(updatedCols.map(c => [c.key, c.visible]));
            writeUrl();
        }

        // Re-fetch when endpoint changes (e.g., page navigation switching tables)
        watch(() => props.endpoint, () => {
            page.value = 1;
            fetchPage();
        });

        onMounted(fetchPage);

        // Expose a `columns-with-visibility` form for ColumnPicker integration
        const columnsForPicker = computed(() =>
            props.columns.map(c => ({ key: c.key, label: c.label, visible: visibility.value[c.key] }))
        );

        return {
            items, total, page, ordering, filters, loading, error,
            totalPages, visibleColumns, columnsForPicker,
            changeSort, ariaSortFor, onFilterInput, gotoPage, toggleColumns,
        };
    },
    template: `
        <div :aria-busy="loading">
            <table class="table table-sm table-hover" :aria-label="ariaLabel">
                <thead>
                    <tr>
                        <th
                            v-for="col in visibleColumns"
                            :key="col.key"
                            scope="col"
                            :aria-sort="col.sortable ? ariaSortFor(col.key) : undefined"
                        >
                            <button
                                v-if="col.sortable"
                                type="button"
                                class="btn btn-sm btn-link p-0 d-inline-flex align-items-center gap-1 fw-semibold text-decoration-none"
                                @click="changeSort(col.key)"
                                :aria-label="'Sort by ' + col.label"
                            >
                                <span>{{ col.label }}</span>
                                <span v-if="ordering === col.key" class="bi bi-arrow-up" aria-hidden="true"></span>
                                <span v-else-if="ordering === '-' + col.key" class="bi bi-arrow-down" aria-hidden="true"></span>
                                <span v-else class="bi bi-arrow-down-up text-muted small" aria-hidden="true"></span>
                            </button>
                            <span v-else class="fw-semibold">{{ col.label }}</span>
                        </th>
                    </tr>
                    <tr v-if="columns.some(c => c.filterable)">
                        <th v-for="col in visibleColumns" :key="col.key" scope="col">
                            <input
                                v-if="col.filterable"
                                type="text"
                                class="form-control form-control-sm"
                                :aria-label="'Filter by ' + col.label"
                                :placeholder="'Filter…'"
                                :value="filters[col.key] || ''"
                                @input="onFilterInput(col.key, $event.target.value)"
                            />
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="loading && items.length === 0">
                        <td :colspan="visibleColumns.length" class="text-center py-3 text-muted">Loading…</td>
                    </tr>
                    <tr v-else-if="error">
                        <td :colspan="visibleColumns.length" class="text-center py-3 text-danger">{{ error }}</td>
                    </tr>
                    <tr v-else-if="items.length === 0">
                        <td :colspan="visibleColumns.length" class="text-center py-3 text-muted">{{ emptyText }}</td>
                    </tr>
                    <tr v-else v-for="(item, idx) in items" :key="item.id ?? idx">
                        <td v-for="col in visibleColumns" :key="col.key">
                            <slot :name="'cell-' + col.key" :item="item" :value="item[col.key]">{{ col.format ? col.format(item[col.key], item) : (item[col.key] ?? '') }}</slot>
                        </td>
                    </tr>
                </tbody>
            </table>
            <div class="d-flex justify-content-between align-items-center small text-muted mt-2">
                <span>{{ total }} total</span>
                <Pagination
                    :page="page"
                    :total-pages="totalPages"
                    @update:page="gotoPage"
                    :aria-label="ariaLabel + ' pagination'"
                />
            </div>
        </div>
    `,
});
