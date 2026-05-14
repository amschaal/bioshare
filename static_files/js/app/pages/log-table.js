// log-table.js — orchestrator for the share/logs.html partial.
// Replaces the AngularJS LogController + ng-table instance. Reusable: any
// page that includes share/logs.html gets a Vue DataTable bound to the
// activity log for one share.
//
// Mount:      #log-table-mount
// Init data:  <script id="log-table-init" type="application/json">
//             { share }   (the 15-char share id)

import { createApp } from 'vue';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';
import { fmtDateShort } from '/static/js/app/format.js';

const initEl = document.getElementById('log-table-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};

const columns = [
    { key: 'timestamp', label: 'Timestamp', sortable: true, visible: true },
    { key: 'action', label: 'Action', sortable: true, filterable: true, filterParam: 'action__icontains', visible: true },
    { key: 'user', label: 'User', sortable: true, filterable: true, filterParam: 'user__username__icontains', ordering: 'user__username', visible: true },
    { key: 'text', label: 'Text', sortable: false, filterable: true, filterParam: 'text__icontains', visible: true },
    { key: 'paths', label: 'Paths', sortable: false, filterable: true, filterParam: 'paths__icontains', visible: true },
];

const mountEl = document.getElementById('log-table-mount');
if (mountEl) {
    createApp({
        components: { DataTable },
        setup() {
            return { columns, baseFilters: { share: init.share }, fmtDateShort };
        },
        template: `
            <DataTable
                endpoint="/bioshare/api/logs/"
                :columns="columns"
                :base-filters="baseFilters"
                :page-size="10"
                aria-label="Share activity log"
                empty-text="No activity logged for this share."
            >
                <template #cell-timestamp="{ item }">{{ fmtDateShort(item.timestamp) }}</template>
                <template #cell-user="{ item }">{{ item.user?.username || '' }}</template>
                <template #cell-paths="{ item }">{{ (item.paths || []).join(', ') }}</template>
            </DataTable>
        `,
    }).mount(mountEl);
}
