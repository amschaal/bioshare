// list.js — orchestrator for the share file browser (templates/list.html).
//
// C2a scope: file browsing. Mounts:
//   - Tabs: Files / Search / Logs
//   - Files tab: FileTable, data loaded from the existing list_directory
//     view's AJAX branch (same URL + X-Requested-With header -> JSON).
//   - Search tab: a simple query form against /api/search/<share>/.
//   - Logs tab: DataTable against /bioshare/api/logs/?share=<id>.
//   - Toolbar: a download DropdownMenu (Zip link).
//
// Deferred to later C2 sub-phases: create folder/link, rename, delete, move,
// edit metadata, upload, file preview, SFTP/rsync/wget dialogs. The FileTable
// action buttons render now (accessible) but their events are no-ops here.

import { createApp, ref, reactive, onMounted } from 'vue';
import { apiGet } from '/static/js/app/api.js';
import { toast } from '/static/js/app/state.js';
import { Tabs } from '/static/js/app/components/Tabs.vue.js';
import { FileTable } from '/static/js/app/components/FileTable.vue.js';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';
import { DropdownMenu, DropdownMenuItem } from '/static/js/app/components/DropdownMenu.vue.js';
import { fmtDateShort } from '/static/js/app/format.js';

const initEl = document.getElementById('list-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};
const mountEl = document.getElementById('file-browser-mount');

if (mountEl) {
    createApp({
        components: { Tabs, FileTable, DataTable, DropdownMenu, DropdownMenuItem },
        setup() {
            const perms = init.perms || [];
            const canWrite = perms.includes('write_to_share');
            const canDownload = perms.includes('download_share_files');

            const activeTab = ref('files');
            const tabs = [
                { value: 'files', label: 'Files' },
                { value: 'search', label: 'Search' },
            ];
            if (init.authenticated) tabs.push({ value: 'logs', label: 'Logs' });

            // ----- Files tab -----
            const directories = ref([]);
            const files = ref([]);
            const loading = ref(true);
            const loadError = ref(null);
            const selection = ref([]);

            async function loadListing() {
                loading.value = true;
                loadError.value = null;
                try {
                    // The list_directory view returns { files, directories }
                    // JSON when called with X-Requested-With: XMLHttpRequest.
                    const r = await fetch(window.location.pathname, {
                        headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
                        credentials: 'same-origin',
                    });
                    if (!r.ok) throw new Error(`Listing failed (${r.status})`);
                    const data = await r.json();
                    files.value = data.files || [];
                    directories.value = Object.values(data.directories || {});
                } catch (e) {
                    loadError.value = e.message || String(e);
                } finally {
                    loading.value = false;
                }
            }

            function dirHref(subdir, name) {
                // Directory links are relative to the current path (matches legacy).
                return `${name}/`;
            }
            function fileHref(name) {
                return init.urls.downloadFilePrefix + encodeURIComponent(name);
            }

            // Row action stubs — wired in later C2 sub-phases.
            function onEditMetadata(_payload) { toast.info('Edit metadata — coming in a later update.'); }
            function onRename(_payload) { toast.info('Rename — coming in a later update.'); }
            function onPreview(_file) { toast.info('Preview — coming in a later update.'); }

            // ----- Search tab -----
            const searchQuery = ref('');
            const searchResults = ref([]);
            const searching = ref(false);
            const searched = ref(false);
            async function runSearch() {
                if (!searchQuery.value.trim()) return;
                searching.value = true;
                searched.value = true;
                try {
                    const r = await apiGet(init.urls.searchApi, { query: searchQuery.value });
                    searchResults.value = r.results || [];
                } catch (e) {
                    searchResults.value = [];
                } finally {
                    searching.value = false;
                }
            }

            // ----- Logs tab -----
            const logColumns = [
                { key: 'timestamp', label: 'Timestamp', sortable: true, visible: true },
                { key: 'action', label: 'Action', sortable: true, filterable: true, filterParam: 'action__icontains', visible: true },
                { key: 'user', label: 'User', sortable: true, filterable: true, filterParam: 'user__username__icontains', ordering: 'user__username', visible: true },
                { key: 'text', label: 'Text', sortable: false, filterable: true, filterParam: 'text__icontains', visible: true },
                { key: 'paths', label: 'Paths', sortable: false, filterable: true, filterParam: 'paths__icontains', visible: true },
            ];

            onMounted(loadListing);

            return {
                canWrite, canDownload, activeTab, tabs,
                directories, files, loading, loadError, selection,
                dirHref, fileHref, onEditMetadata, onRename, onPreview,
                searchQuery, searchResults, searching, searched, runSearch,
                logColumns, init, fmtDateShort,
            };
        },
        template: `
            <div>
                <div class="d-flex flex-wrap gap-2 mb-3" v-if="canDownload || canWrite">
                    <DropdownMenu v-if="canDownload" label="Download" variant="primary">
                        <DropdownMenuItem @select="() => window.location = init.urls.downloadZip">Zip file (up to 2 GB)</DropdownMenuItem>
                    </DropdownMenu>
                </div>

                <Tabs v-model="activeTab" :tabs="tabs" aria-label="File browser sections">
                    <template #files>
                        <p v-if="loading" class="text-muted">Loading files…</p>
                        <p v-else-if="loadError" class="text-danger">{{ loadError }}</p>
                        <FileTable
                            v-else
                            :directories="directories"
                            :files="files"
                            :subdir="init.subdir || ''"
                            :can-write="canWrite"
                            :can-download="canDownload"
                            :dir-href="dirHref"
                            :file-href="fileHref"
                            @selection-change="sel => selection = sel"
                            @edit-metadata="onEditMetadata"
                            @rename="onRename"
                            @preview="onPreview"
                        />
                    </template>

                    <template #search>
                        <ul class="text-muted small">
                            <li>Use "*" for wildcard</li>
                            <li>Search is case sensitive</li>
                        </ul>
                        <form class="d-flex gap-2 mb-3" @submit.prevent="runSearch">
                            <label for="file-search-box" class="visually-hidden">Search files in this share</label>
                            <input id="file-search-box" v-model="searchQuery" class="form-control" style="max-width: 24rem;" placeholder="Search files…" />
                            <button type="submit" class="btn btn-primary" :disabled="searching">Search</button>
                        </form>
                        <div aria-live="polite">
                            <p v-if="searching" class="text-muted">Searching…</p>
                            <p v-else-if="searched && searchResults.length === 0" class="text-muted">No matches.</p>
                            <ul v-else-if="searchResults.length" class="list-unstyled">
                                <li v-for="(path, i) in searchResults" :key="i">
                                    <span class="bi bi-file-earmark me-1" aria-hidden="true"></span>{{ path }}
                                </li>
                            </ul>
                        </div>
                    </template>

                    <template #logs>
                        <DataTable
                            :endpoint="init.urls.logsApi"
                            :columns="logColumns"
                            :base-filters="{ share: init.share }"
                            :page-size="10"
                            aria-label="Share activity log"
                            empty-text="No activity logged for this share."
                        >
                            <template #cell-timestamp="{ item }">{{ fmtDateShort(item.timestamp) }}</template>
                            <template #cell-user="{ item }">{{ item.user?.username || '' }}</template>
                            <template #cell-paths="{ item }">{{ (item.paths || []).join(', ') }}</template>
                        </DataTable>
                    </template>
                </Tabs>
            </div>
        `,
    }).mount(mountEl);
}
