// groups.js — orchestrator for groups/groups.html (the groups list).
// Replaces the AngularJS GroupsController + ng-table instance.
//
// Mount: #groups-page-mount

import { createApp, reactive } from 'vue';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';

const mountEl = document.getElementById('groups-page-mount');
if (mountEl) {
    createApp({
        components: { DataTable },
        setup() {
            const columns = reactive([
                { key: 'name', label: 'Name', sortable: true, filterable: true, filterParam: 'name__icontains', visible: true },
            ]);
            return { columns };
        },
        template: `
            <DataTable
                endpoint="/bioshare/api/groups/"
                :columns="columns"
                :page-size="10"
                url-state-key="groups-table"
                aria-label="Groups"
                empty-text="No groups match these filters."
            >
                <template #cell-name="{ item }">
                    <a :href="'/bioshare/groups/' + item.id + '/'">{{ item.name }}</a>
                </template>
            </DataTable>
        `,
    }).mount(mountEl);
}
