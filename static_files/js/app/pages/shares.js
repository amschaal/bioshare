// shares.js — orchestrator for share/shares.html (the main shares list).
// Replaces the AngularJS SharesController + ng-table instance.
//
// Mount: #shares-page-mount
// Init data:  <script id="shares-init" type="application/json">{...}</script>
//             keys: locked (bool), bad_paths (bool), group (string|null),
//                   ownsShares (bool — whether to show the Advanced Filters panel)

import { createApp, ref, reactive, computed, watch } from 'vue';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';
import { ColumnPicker } from '/static/js/app/components/ColumnPicker.vue.js';
import { fmtBytes, fmtDateShort } from '/static/js/app/format.js';
import { getUrlState, mergeUrlState } from '/static/js/app/url-state.js';

const initEl = document.getElementById('shares-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};

const ADV_URL_KEY = 'shares-adv';
const truthy = v => v === true || v === 'true';

const mountEl = document.getElementById('shares-page-mount');
if (mountEl) {
    createApp({
        components: { DataTable, ColumnPicker },
        setup() {
            // Default visibility mirrors the legacy SharesController.cols defaults.
            const columns = reactive([
                { key: 'name',                label: 'Share',       sortable: true,  filterable: true, filterParam: 'name__icontains', visible: true },
                { key: 'notes',               label: 'Description', sortable: false, filterable: true, filterParam: 'notes__icontains', visible: true },
                { key: 'tags',                label: 'Tags',        sortable: false, filterable: true, filterParam: 'tags',            visible: true },
                { key: 'owner',               label: 'Owner',       sortable: true,  filterable: true, filterParam: 'owner__username__icontains', ordering: 'owner__username', visible: true },
                { key: 'users',               label: 'Users',       sortable: false, filterable: true, filterParam: 'user',            visible: false },
                { key: 'groups',              label: 'Groups',      sortable: false, filterable: true, filterParam: 'group',           visible: false },
                { key: 'created',             label: 'Created',     sortable: true,  filterable: false, visible: false },
                { key: 'updated',             label: 'Modified',    sortable: true,  filterable: false, visible: true },
                { key: 'stats.num_files',     label: 'Files',       sortable: true,  filterable: false, ordering: 'stats__num_files', visible: false },
                { key: 'stats.bytes',         label: 'Size',        sortable: true,  filterable: false, ordering: 'stats__bytes',     visible: true },
            ]);

            // Context filters fixed by the page URL (?bad_paths, group pages).
            // Not user-editable; always applied. `locked` is handled in the
            // Advanced Filters panel instead so the user can toggle it.
            const contextFilters = {};
            if (init.bad_paths) contextFilters.path_exists = 'false';
            if (init.group) contextFilters.group = init.group;

            // Advanced Filters — the collapsible panel restored from the legacy
            // SharesController.filters / filter_labels. Seeded from init (the
            // ?locked page pre-checks "Locked") and from URL state (bookmarks).
            const urlAdv = getUrlState()[ADV_URL_KEY] || {};
            const advanced = reactive({
                locked:              !!init.locked || truthy(urlAdv.locked),
                contains_symlinks:   truthy(urlAdv.contains_symlinks),
                has_symlink_warning: truthy(urlAdv.has_symlink_warning),
                symlink_target:      typeof urlAdv.symlink_target === 'string' ? urlAdv.symlink_target : '',
            });

            // Local model for the text input; debounced into `advanced` so a
            // refetch doesn't fire on every keystroke (matches DataTable's
            // column-filter debounce).
            const symlinkTargetInput = ref(advanced.symlink_target);
            let symlinkTimer = null;
            watch(symlinkTargetInput, v => {
                if (symlinkTimer) clearTimeout(symlinkTimer);
                symlinkTimer = setTimeout(() => { advanced.symlink_target = v; }, 400);
            });

            // Show the panel expanded when arriving with a filter already active
            // (e.g. a bookmarked filtered view).
            const showFilters = ref(
                advanced.contains_symlinks || advanced.has_symlink_warning ||
                !!advanced.symlink_target || (advanced.locked && !init.locked)
            );

            // Everything the DataTable applies on top of the column filters.
            const baseFilters = computed(() => {
                const f = { ...contextFilters };
                if (advanced.locked) f.locked = 'true';
                if (advanced.contains_symlinks) f.contains_symlinks = 'true';
                if (advanced.has_symlink_warning) f.has_symlink_warning = 'true';
                const target = advanced.symlink_target.trim();
                if (target) f.symlink_target = target;
                return f;
            });

            // Persist the advanced filters to URL state so the view is
            // bookmarkable. Only truthy values are written.
            watch(advanced, () => {
                const out = {};
                if (advanced.locked) out.locked = true;
                if (advanced.contains_symlinks) out.contains_symlinks = true;
                if (advanced.has_symlink_warning) out.has_symlink_warning = true;
                const target = advanced.symlink_target.trim();
                if (target) out.symlink_target = target;
                mergeUrlState({ [ADV_URL_KEY]: out });
            }, { deep: true });

            return {
                columns, baseFilters, advanced, symlinkTargetInput, showFilters,
                ownsShares: !!init.ownsShares,
                fmtBytes, fmtDateShort,
            };
        },
        template: `
            <div>
                <ColumnPicker :columns="columns" legend="Columns" />

                <div v-if="ownsShares" class="mt-2 mb-3">
                    <button
                        type="button"
                        class="btn btn-link p-0 text-decoration-none"
                        :aria-expanded="showFilters"
                        aria-controls="advanced-filters-panel"
                        @click="showFilters = !showFilters"
                    >
                        <span :class="showFilters ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" aria-hidden="true"></span>
                        {{ showFilters ? 'Hide' : 'Show' }} advanced filters
                    </button>
                    <fieldset v-show="showFilters" id="advanced-filters-panel" class="border rounded p-3 mt-2">
                        <legend class="float-none w-auto px-2 fs-6 mb-0">Advanced filters</legend>
                        <div class="d-flex flex-wrap gap-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="filter-locked" v-model="advanced.locked" />
                                <label class="form-check-label" for="filter-locked">Locked</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="filter-contains-symlinks" v-model="advanced.contains_symlinks" />
                                <label class="form-check-label" for="filter-contains-symlinks">Contains symlink</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="filter-bad-symlink" v-model="advanced.has_symlink_warning" />
                                <label class="form-check-label" for="filter-bad-symlink">Contains bad symlink</label>
                            </div>
                        </div>
                        <div class="mt-3" style="max-width: 28rem;">
                            <label class="form-label" for="filter-symlink-target">Symlink target contains</label>
                            <input
                                type="text"
                                class="form-control form-control-sm"
                                id="filter-symlink-target"
                                v-model="symlinkTargetInput"
                                placeholder="e.g. /shared/data"
                            />
                            <div class="form-text">Only show shares with a symlink whose target contains this text.</div>
                        </div>
                    </fieldset>
                </div>

                <DataTable
                    endpoint="/bioshare/api/shares/"
                    :columns="columns"
                    :base-filters="baseFilters"
                    :page-size="10"
                    url-state-key="shares-table"
                    aria-label="Shares"
                    empty-text="No shares match these filters."
                    class="mt-3"
                >
                    <template #cell-name="{ item }">
                        <a v-if="item.path_exists && !item.locked" :href="item.url">{{ item.name }}</a>
                        <span v-else-if="!item.path_exists" class="error" title="Share path does not exist">
                            <i class="bi bi-exclamation-triangle" aria-hidden="true"></i> {{ item.name }}
                        </span>
                        <a v-else :href="item.url" class="error" title="Share has been locked">
                            <i class="bi bi-lock" aria-hidden="true"></i> {{ item.name }}
                        </a>
                    </template>
                    <template #cell-tags="{ item }">{{ (item.tags || []).map(t => t.name).join(', ') }}</template>
                    <template #cell-owner="{ item }">{{ item.owner?.username || '' }}</template>
                    <template #cell-users="{ item }">
                        <span v-for="(u, i) in (item.users || [])" :key="i">{{ u }}<template v-if="i < item.users.length - 1">, </template></span>
                    </template>
                    <template #cell-groups="{ item }">
                        <span v-for="(g, i) in (item.groups || [])" :key="i">{{ g }}<template v-if="i < item.groups.length - 1">, </template></span>
                    </template>
                    <template #cell-created="{ item }">{{ fmtDateShort(item.created) }}</template>
                    <template #cell-updated="{ item }">{{ fmtDateShort(item.updated) }}</template>
                    <template #cell-stats.num_files="{ item }">{{ item.stats?.num_files ?? '-' }}</template>
                    <template #cell-stats.bytes="{ item }">{{ item.stats?.bytes != null ? fmtBytes(item.stats.bytes) : '-' }}</template>
                </DataTable>
            </div>
        `,
    }).mount(mountEl);
}
