// list.js — orchestrator for the share file browser (templates/list.html).
//
// C2a: file browsing — Tabs (Files / Search / Logs), FileTable, Logs DataTable.
// C2b: create folder, rename, delete, edit metadata — Modal + ConfirmDialog.
//
// Data: the Files tab loads from the list_directory view's AJAX branch (same
// URL + X-Requested-With header -> { files, directories, errors } JSON).
//
// Deferred to later C2 sub-phases: upload + progress, move-to, file preview,
// create symlink, and the SFTP/rsync/wget/email/share-read-only dialogs.

import { createApp, ref, computed, onMounted } from 'vue';
import { apiGet, apiPost } from '/static/js/app/api.js';
import { toast, confirm as openConfirm } from '/static/js/app/state.js';
import { Tabs } from '/static/js/app/components/Tabs.vue.js';
import { FileTable } from '/static/js/app/components/FileTable.vue.js';
import { DataTable } from '/static/js/app/components/DataTable.vue.js';
import { DropdownMenu, DropdownMenuItem } from '/static/js/app/components/DropdownMenu.vue.js';
import { Modal } from '/static/js/app/components/Modal.vue.js';
import { Uploader } from '/static/js/app/components/Uploader.vue.js';
import { fmtDateShort } from '/static/js/app/format.js';

const initEl = document.getElementById('list-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};
const mountEl = document.getElementById('file-browser-mount');

// POST a form-urlencoded body. Several legacy file_views read request.POST
// (not request.data), so they need multipart/form-data, not JSON.
function formPost(url, fields) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    return apiPost(url, fd);
}

if (mountEl) {
    createApp({
        components: { Tabs, FileTable, DataTable, DropdownMenu, DropdownMenuItem, Modal, Uploader },
        setup() {
            const perms = init.perms || [];
            const canWrite = perms.includes('write_to_share');
            const canDownload = perms.includes('download_share_files');
            const canDelete = perms.includes('delete_share_files');

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

            const dirHref = (subdir, name) => `${name}/`;
            const fileHref = (name) => init.urls.downloadFilePrefix + encodeURIComponent(name);

            // ----- Uploader -----
            const showUploader = ref(false);
            function onUploaded(fileObj) {
                // Server descriptor: { name, extension, size, bytes, url, modified, isText }.
                // Replace an existing same-named row (re-upload) or append.
                const existing = files.value.findIndex(f => f.name === fileObj.name);
                const row = { ...fileObj, metadata: {} };
                if (existing !== -1) files.value.splice(existing, 1, row);
                else files.value.push(row);
            }
            function onUploadFailed(name, message) {
                toast.error(`${name}: ${message}`);
            }

            // ----- New Folder modal -----
            const folderModalOpen = ref(false);
            const folderName = ref('');
            const folderError = ref('');
            const folderSaving = ref(false);
            function openFolderModal() {
                folderName.value = '';
                folderError.value = '';
                folderModalOpen.value = true;
            }
            async function createFolder() {
                if (!folderName.value.trim()) { folderError.value = 'Enter a folder name.'; return; }
                folderSaving.value = true;
                folderError.value = '';
                try {
                    const data = await formPost(init.urls.createFolder, { name: folderName.value.trim() });
                    if (data.errors && data.errors.length) {
                        folderError.value = data.errors.join(' ');
                        return;
                    }
                    for (const obj of (data.objects || [])) {
                        directories.value.push({ name: obj.name, modified: obj.modified, metadata: {} });
                    }
                    folderModalOpen.value = false;
                    toast.success(`Folder "${folderName.value.trim()}" created.`);
                } catch (e) {
                    folderError.value = e?.body?.errors?.join(' ') || e.message || 'Could not create folder.';
                } finally {
                    folderSaving.value = false;
                }
            }

            // ----- Rename modal -----
            const renameModalOpen = ref(false);
            const renameTarget = ref(null); // { type, row }
            const renameTo = ref('');
            const renameError = ref('');
            const renameSaving = ref(false);
            function openRename({ type, row }) {
                renameTarget.value = { type, row };
                renameTo.value = row.name;
                renameError.value = '';
                renameModalOpen.value = true;
            }
            async function doRename() {
                const from = renameTarget.value?.row?.name;
                const to = renameTo.value.trim();
                if (!to) { renameError.value = 'Enter a new name.'; return; }
                if (to === from) { renameModalOpen.value = false; return; }
                renameSaving.value = true;
                renameError.value = '';
                try {
                    const data = await formPost(init.urls.modifyName, { from_name: from, to_name: to });
                    if (data.errors && data.errors.length) {
                        renameError.value = data.errors.join(' ');
                        return;
                    }
                    const list = renameTarget.value.type === 'directory' ? directories.value : files.value;
                    const item = list.find(x => x.name === from);
                    if (item) item.name = to;
                    renameModalOpen.value = false;
                    toast.success(`Renamed to "${to}".`);
                } catch (e) {
                    renameError.value = e?.body?.errors?.join(' ') || e.message || 'Could not rename.';
                } finally {
                    renameSaving.value = false;
                }
            }

            // ----- Delete (global ConfirmDialog) -----
            async function deleteSelected() {
                const sel = selection.value.slice();
                if (sel.length === 0) return;
                const ok = await openConfirm({
                    title: `Delete ${sel.length} item${sel.length > 1 ? 's' : ''}?`,
                    message: `This permanently deletes: ${sel.join(', ')}. This cannot be undone.`,
                    confirmLabel: 'Delete',
                    danger: true,
                });
                if (!ok) return;
                try {
                    const data = await apiPost(init.urls.deletePaths, { selection: sel });
                    const deleted = new Set(data.deleted || []);
                    directories.value = directories.value.filter(d => !deleted.has(d.name));
                    files.value = files.value.filter(f => !deleted.has(f.name));
                    selection.value = [];
                    if ((data.failed || []).length) {
                        toast.warning(`Deleted ${data.deleted.length}; failed: ${data.failed.join(', ')}`);
                    } else {
                        toast.success(`Deleted ${data.deleted.length} item${data.deleted.length > 1 ? 's' : ''}.`);
                    }
                } catch (e) {
                    toast.error(e.message || 'Delete failed.');
                }
            }

            // ----- Edit Metadata modal -----
            const metaModalOpen = ref(false);
            const metaTarget = ref(null); // { type, row }
            const metaNotes = ref('');
            const metaTags = ref('');
            const metaError = ref('');
            const metaSaving = ref(false);
            function openMetadata({ type, row }) {
                metaTarget.value = { type, row };
                metaNotes.value = row.metadata?.notes || '';
                const tags = row.metadata?.tags;
                metaTags.value = Array.isArray(tags) ? tags.join(', ') : '';
                metaError.value = '';
                metaModalOpen.value = true;
            }
            async function saveMetadata() {
                const row = metaTarget.value?.row;
                if (!row) return;
                metaSaving.value = true;
                metaError.value = '';
                try {
                    // edit_metadata URL is metadataPrefix + <name> (subdir already baked into prefix).
                    const url = init.urls.metadataPrefix + encodeURIComponent(row.name);
                    const data = await formPost(url, { notes: metaNotes.value, tags: metaTags.value });
                    if (data.errors && data.errors.length) {
                        metaError.value = data.errors.join(' ');
                        return;
                    }
                    row.metadata = { notes: data.notes, tags: data.tags || [] };
                    metaModalOpen.value = false;
                    toast.success(`Metadata saved for "${row.name}".`);
                } catch (e) {
                    metaError.value = e?.body?.errors?.join(' ') || e.message || 'Could not save metadata.';
                } finally {
                    metaSaving.value = false;
                }
            }

            function onPreview(_file) { toast.info('File preview — coming in a later update.'); }

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
                canWrite, canDownload, canDelete,
                activeTab, tabs,
                directories, files, loading, loadError, selection,
                dirHref, fileHref, onPreview,
                showUploader, onUploaded, onUploadFailed,
                folderModalOpen, folderName, folderError, folderSaving, openFolderModal, createFolder,
                renameModalOpen, renameTarget, renameTo, renameError, renameSaving, openRename, doRename,
                deleteSelected,
                metaModalOpen, metaTarget, metaNotes, metaTags, metaError, metaSaving, openMetadata, saveMetadata,
                searchQuery, searchResults, searching, searched, runSearch,
                logColumns, init, fmtDateShort,
            };
        },
        template: `
            <div>
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <DropdownMenu v-if="canDownload" label="Download" variant="primary">
                        <DropdownMenuItem @select="() => window.location = init.urls.downloadZip">Zip file (up to 2 GB)</DropdownMenuItem>
                    </DropdownMenu>
                    <button v-if="canWrite" type="button" class="btn btn-success" @click="openFolderModal">
                        <span class="bi bi-folder-plus me-1" aria-hidden="true"></span>New folder
                    </button>
                    <button
                        v-if="canWrite"
                        type="button"
                        class="btn btn-success"
                        :aria-expanded="showUploader"
                        aria-controls="file-uploader-panel"
                        @click="showUploader = !showUploader"
                    >
                        <span class="bi bi-upload me-1" aria-hidden="true"></span>Upload
                    </button>
                    <button v-if="canDelete" type="button" class="btn btn-danger" :disabled="selection.length === 0" @click="deleteSelected">
                        <span class="bi bi-trash me-1" aria-hidden="true"></span>Delete<span v-if="selection.length"> ({{ selection.length }})</span>
                    </button>
                </div>

                <div v-if="canWrite && showUploader" id="file-uploader-panel" class="mb-3">
                    <Uploader
                        :url="init.urls.uploadFile"
                        @uploaded="onUploaded"
                        @failed="onUploadFailed"
                        @all-done="() => {}"
                    />
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
                            @edit-metadata="openMetadata"
                            @rename="openRename"
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

                <!-- New Folder modal -->
                <Modal v-model:open="folderModalOpen" title="New folder" size="sm">
                    <form @submit.prevent="createFolder">
                        <label for="new-folder-name" class="form-label">Folder name</label>
                        <input id="new-folder-name" v-model="folderName" class="form-control" :class="{ 'is-invalid': folderError }" autocomplete="off" />
                        <div v-if="folderError" class="invalid-feedback d-block">{{ folderError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="folderModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="folderSaving" @click="createFolder">Create</button>
                    </template>
                </Modal>

                <!-- Rename modal -->
                <Modal v-model:open="renameModalOpen" :title="renameTarget ? 'Rename &quot;' + renameTarget.row.name + '&quot;' : 'Rename'" size="sm">
                    <form @submit.prevent="doRename">
                        <label for="rename-to" class="form-label">New name</label>
                        <input id="rename-to" v-model="renameTo" class="form-control" :class="{ 'is-invalid': renameError }" autocomplete="off" />
                        <div v-if="renameError" class="invalid-feedback d-block">{{ renameError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="renameModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="renameSaving" @click="doRename">Rename</button>
                    </template>
                </Modal>

                <!-- Edit Metadata modal -->
                <Modal v-model:open="metaModalOpen" :title="metaTarget ? 'Metadata for &quot;' + metaTarget.row.name + '&quot;' : 'Metadata'" size="md">
                    <form @submit.prevent="saveMetadata">
                        <div class="mb-3">
                            <label for="meta-notes" class="form-label">Notes</label>
                            <textarea id="meta-notes" v-model="metaNotes" class="form-control" rows="4"></textarea>
                        </div>
                        <div>
                            <label for="meta-tags" class="form-label">Tags</label>
                            <textarea id="meta-tags" v-model="metaTags" class="form-control" rows="2" placeholder="comma-separated, e.g. important, chimpanzee"></textarea>
                        </div>
                        <div v-if="metaError" class="text-danger mt-2">{{ metaError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="metaModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="metaSaving" @click="saveMetadata">Save</button>
                    </template>
                </Modal>
            </div>
        `,
    }).mount(mountEl);
}
