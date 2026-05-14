// shares.js — orchestrator for share/shares.html (the main shares list).
// Replaces the AngularJS SharesController + ng-table instance.
//
// Mount: #shares-page-mount
// Init data:  <script id="shares-init" type="application/json">{...}</script>
//             keys: locked (bool), bad_paths (bool), group (string|null)

import { createApp, ref, reactive, computed, h } from 'vue';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';
import { ColumnPicker } from '/static/js/app/components/ColumnPicker.vue.js';
import { fmtBytes, fmtDateShort } from '/static/js/app/format.js';

const initEl = document.getElementById('shares-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};

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

            // Map init flags to filterable params accepted by /api/shares/
            // The endpoint accepts ?locked=true, ?path_exists=false (filterset_fields), ?group=<name> (GroupShareFilter).
            const baseFilters = {};
            if (init.locked) baseFilters.locked = 'true';
            if (init.bad_paths) baseFilters.path_exists = 'false';
            if (init.group) baseFilters.group = init.group;

            // Pass-through helpers for the cell slots.
            return { columns, baseFilters, fmtBytes, fmtDateShort };
        },
        template: `
            <div>
                <ColumnPicker :columns="columns" legend="Columns" />

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
