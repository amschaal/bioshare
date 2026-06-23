// list.js — orchestrator for the share file browser (templates/list.html).
//
// C2a: file browsing — Tabs (Files / Search / Logs), FileTable, Logs DataTable.
// C2b: create folder, rename, delete, edit metadata — Modal + ConfirmDialog.
// C2c: file upload — Uploader + ProgressBar.
// C2d: move-to + file preview — Modal.
// C2e: create symlink, email participants, share read-only, and the
//      SFTP / rsync / wget connection-info dialogs.
//
// Data: the Files tab loads from the list_directory view's AJAX branch (same
// URL + X-Requested-With header -> { files, directories, errors } JSON).

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
function formPost(url, fields, opts) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    return apiPost(url, fd, opts);
}

// Extract a readable error string from a 200-status response body that
// still carries validation errors. json_form_validate sets data.errors as
// a dict { fieldName: ErrorList }; some endpoints (e.g. modify_name) always
// return 200 even when the form is invalid. Returns '' when there are none.
function formErrorText(data) {
    if (!data || data.status !== 'error' || !data.errors) return '';
    const errs = data.errors;
    let parts = [];
    if (Array.isArray(errs)) {
        parts = errs.flat(Infinity);
    } else if (typeof errs === 'object') {
        parts = Object.values(errs).flat(Infinity);
    }
    return parts.map(x => String(x)).filter(Boolean).join(' ');
}

if (mountEl) {
    createApp({
        components: { Tabs, FileTable, DataTable, DropdownMenu, DropdownMenuItem, Modal, Uploader },
        setup() {
            const perms = init.perms || [];
            const canWrite = perms.includes('write_to_share');
            const canDownload = perms.includes('download_share_files');
            const canDelete = perms.includes('delete_share_files');
            const canLink = !!init.canLink && canWrite;
            const canEmail = perms.includes('write_to_share') || perms.includes('admin');
            const canShareReadOnly = perms.includes('share_read_only');
            const canAdmin = perms.includes('admin');
            // Linked/symlinked directories can't be resharred or unlinked (matches
            // the legacy `is_realpath` gate). `isSubshare` is true when the share
            // being viewed is itself a subshare of another share.
            const isRealpath = init.isRealpath !== false;
            const isSubshare = !!init.isSubshare;
            // The current directory may be published as its own subshare when the
            // user is an admin, we're inside a subdirectory, this view isn't
            // already a subshare, and the directory is a real path (not a symlink).
            const canCreateSubshare = canAdmin && !!init.subdir && !isSubshare && isRealpath;
            // create_subshare's <subdir> URL group requires a trailing slash, so it
            // can't be reversed empty; the template reverses a placeholder we strip
            // here to get a clean base (preserving Django's real URL prefix).
            const createSubshareBase = (init.urls.createSubshareBase || '').replace('SUBDIR_PLACEHOLDER/', '');
            // create_subshare URL for a directory row: base + current subdir + name + '/'
            const subshareHref = (name) => createSubshareBase + (init.subdir || '') + name + '/';
            const subshareCurrentHref = createSubshareBase + (init.subdir || '');

            // Connection-info command strings (computed from server context;
            // mirror the legacy main.js generate_rsync_* / generate_wget_*).
            const conn = init.conn || {};
            const rsyncPath = '/' + init.share + '/' + (init.subdir || '');
            const sftpAvailable = !!(conn.host && conn.sftpPort);
            const rsyncAvailable = !!conn.rsyncUrl;
            const wgetArgs = '-r --level=10 -nH -nc --cut-dirs=3 --no-parent --reject "wget_index.html" --no-check-certificate --header "Cookie: sessionid=' + conn.sessionCookie + ';" https://' + conn.baseUrl + '/bioshare/wget' + rsyncPath + 'wget_index.html';
            const connStrings = {
                sftp: 'sftp -P ' + conn.sftpPort + " '" + conn.username + "'@" + conn.host + ':/' + conn.shareSlug,
                rsyncDownload: 'rsync -vrt ' + conn.rsyncUrl + ':' + rsyncPath + ' /to/my/local/directory',
                rsyncUpload: 'rsync -vrt --no-p --no-g --chmod=ugo=rwX /path/to/my/files ' + conn.rsyncUrl + ':' + rsyncPath,
                wgetLinux: 'wget ' + wgetArgs,
                wgetWindows: '"C:\\Program Files\\GnuWin32\\bin\\wget.exe" ' + wgetArgs,
            };

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
                    const data = await formPost(init.urls.createFolder, { name: folderName.value.trim() }, { suppressErrorToast: true });
                    const formErr = formErrorText(data);
                    if (formErr) { folderError.value = formErr; return; }
                    for (const obj of (data.objects || [])) {
                        directories.value.push({ name: obj.name, modified: obj.modified, metadata: {} });
                    }
                    folderModalOpen.value = false;
                    toast.success(`Folder "${folderName.value.trim()}" created.`);
                } catch (e) {
                    folderError.value = e.message || 'Could not create folder.';
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
                    const data = await formPost(init.urls.modifyName, { from_name: from, to_name: to }, { suppressErrorToast: true });
                    const formErr = formErrorText(data);
                    if (formErr) { renameError.value = formErr; return; }
                    const list = renameTarget.value.type === 'directory' ? directories.value : files.value;
                    const item = list.find(x => x.name === from);
                    if (item) item.name = to;
                    renameModalOpen.value = false;
                    toast.success(`Renamed to "${to}".`);
                } catch (e) {
                    renameError.value = e.message || 'Could not rename.';
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
                    const data = await formPost(url, { notes: metaNotes.value, tags: metaTags.value }, { suppressErrorToast: true });
                    const formErr = formErrorText(data);
                    if (formErr) { metaError.value = formErr; return; }
                    row.metadata = { notes: data.notes, tags: data.tags || [] };
                    metaModalOpen.value = false;
                    toast.success(`Metadata saved for "${row.name}".`);
                } catch (e) {
                    metaError.value = e.message || 'Could not save metadata.';
                } finally {
                    metaSaving.value = false;
                }
            }

            // ----- Move modal -----
            const moveModalOpen = ref(false);
            const moveDestination = ref('');
            const moveError = ref('');
            const moveSaving = ref(false);
            function openMoveModal() {
                if (selection.value.length === 0) return;
                moveDestination.value = '';
                moveError.value = '';
                moveModalOpen.value = true;
            }
            async function doMove() {
                const dest = moveDestination.value.trim();
                if (!dest) { moveError.value = 'Enter a destination folder.'; return; }
                moveSaving.value = true;
                moveError.value = '';
                try {
                    const data = await apiPost(init.urls.movePaths, {
                        json: { destination: dest, selection: selection.value.slice() },
                    });
                    const moved = new Set(data.moved || []);
                    directories.value = directories.value.filter(d => !moved.has(d.name));
                    files.value = files.value.filter(f => !moved.has(f.name));
                    selection.value = [];
                    moveModalOpen.value = false;
                    if ((data.failed || []).length) {
                        toast.warning(`Moved ${data.moved.length}; failed: ${data.failed.join(', ')}`);
                    } else {
                        toast.success(`Moved ${data.moved.length} item${data.moved.length > 1 ? 's' : ''} to "${dest}".`);
                    }
                } catch (e) {
                    moveError.value = e.message || 'Move failed.';
                } finally {
                    moveSaving.value = false;
                }
            }

            // ----- File Preview modal -----
            const PREVIEW_CHUNK = 200;
            const previewModalOpen = ref(false);
            const previewFile = ref(null);
            const previewContent = ref('');
            const previewLoading = ref(false);
            const previewFrom = ref(1);
            const previewTotal = ref(null);
            const previewHasMore = ref(false);
            async function loadPreviewChunk(includeTotal) {
                if (!previewFile.value) return;
                previewLoading.value = true;
                try {
                    const url = init.urls.previewPrefix + encodeURIComponent(previewFile.value.name);
                    const params = { from: previewFrom.value, for: PREVIEW_CHUNK };
                    if (includeTotal) params.get_total = '1';
                    const data = await apiGet(url, params);
                    const chunk = Array.isArray(data.content) ? data.content.join('') : (data.content || '');
                    previewContent.value += chunk;
                    if (data.total != null) previewTotal.value = data.total;
                    previewFrom.value = data.next?.from || (previewFrom.value + PREVIEW_CHUNK);
                    previewHasMore.value = previewTotal.value != null && previewFrom.value <= previewTotal.value;
                } catch (e) {
                    previewContent.value = 'Unable to preview this file.';
                    previewHasMore.value = false;
                } finally {
                    previewLoading.value = false;
                }
            }
            async function onPreview(file) {
                previewFile.value = file;
                previewContent.value = '';
                previewFrom.value = 1;
                previewTotal.value = null;
                previewHasMore.value = false;
                previewModalOpen.value = true;
                await loadPreviewChunk(true);
            }

            // ----- Create Symlink modal -----
            const linkModalOpen = ref(false);
            const linkName = ref('');
            const linkTarget = ref('');
            const linkError = ref('');
            const linkSaving = ref(false);
            function openLinkModal() {
                linkName.value = '';
                linkTarget.value = '';
                linkError.value = '';
                linkModalOpen.value = true;
            }
            async function createSymlink() {
                const name = linkName.value.trim();
                const target = linkTarget.value.trim();
                if (!name || !target) { linkError.value = 'Both a link name and a target path are required.'; return; }
                linkSaving.value = true;
                linkError.value = '';
                try {
                    // create_symlink reads request.data — JSON is fine. It
                    // returns json_error (HTTP 400) on an invalid target/name,
                    // so apiPost throws and the catch below surfaces the
                    // specific message ("Bad path", "Path not allowed", etc.)
                    // in the modal instead of a generic server-error toast.
                    const data = await apiPost(init.urls.createSymlink, { name, target }, { suppressErrorToast: true });
                    const formErr = formErrorText(data);
                    if (formErr) { linkError.value = formErr; return; }
                    for (const obj of (data.objects || [])) {
                        if (obj.type === 'directory') {
                            directories.value.push({ name: obj.name, modified: obj.modified, metadata: {}, target: obj.target });
                        } else {
                            // symlink to a file shows in the directories list with a target (matches legacy)
                            directories.value.push({ name: obj.name, modified: obj.modified, metadata: {}, target: obj.target });
                        }
                    }
                    linkModalOpen.value = false;
                    toast.success(`Link "${name}" created.`);
                } catch (e) {
                    linkError.value = e.message || 'Could not create link.';
                } finally {
                    linkSaving.value = false;
                }
            }

            // ----- Unlink directory (symlink) -----
            async function unlinkDirectory(dir) {
                const ok = await openConfirm({
                    title: 'Unlink directory?',
                    message: `This removes the symlink "${dir.name}" from this share. The files it points to are not deleted.`,
                    confirmLabel: 'Unlink',
                    danger: true,
                });
                if (!ok) return;
                try {
                    // The unlink view reads no body and isn't method-restricted; a
                    // GET avoids CSRF and matches the legacy behaviour. It returns
                    // json_error (HTTP 400) if there's no symlink at the path.
                    const url = init.urls.unlinkBase + (init.subdir || '') + dir.name;
                    await apiGet(url, null, { suppressErrorToast: true });
                    directories.value = directories.value.filter(d => d.name !== dir.name);
                    toast.success(`Unlinked "${dir.name}".`);
                } catch (e) {
                    toast.error(e.message || 'Could not unlink directory.');
                }
            }

            // ----- Email Participants modal -----
            const emailModalOpen = ref(false);
            const emailAllRecipients = ref(true);
            const emailSelected = ref([]); // when not "all"
            const emailSubject = ref('');
            const emailBody = ref('');
            const emailSending = ref(false);
            const emailError = ref('');
            const emailRecipients = init.email?.recipients || [];
            function openEmailModal() {
                emailAllRecipients.value = true;
                emailSelected.value = [];
                emailSubject.value = init.email?.defaultSubject || '';
                emailBody.value = init.email?.defaultBody || '';
                emailError.value = '';
                emailModalOpen.value = true;
            }
            async function sendEmail() {
                emailSending.value = true;
                emailError.value = '';
                try {
                    const fields = { subject: emailSubject.value, body: emailBody.value };
                    // email_participants reads request.POST.getlist('emails'); empty list means "all".
                    const fd = new FormData();
                    fd.append('subject', emailSubject.value);
                    fd.append('body', emailBody.value);
                    if (!emailAllRecipients.value) {
                        for (const e of emailSelected.value) fd.append('emails', e);
                    }
                    const data = await apiPost(init.urls.emailParticipants, fd);
                    emailModalOpen.value = false;
                    toast.success(`Emailed: ${(data.sent_to || []).join(', ')}`);
                } catch (e) {
                    emailError.value = e?.body?.errors?.join(' ') || e.message || 'Could not send email.';
                } finally {
                    emailSending.value = false;
                }
            }

            // ----- Share Read-Only modal -----
            const shareROModalOpen = ref(false);
            const shareROEmail = ref('');
            const shareROError = ref('');
            const shareROSaving = ref(false);
            function openShareROModal() {
                shareROEmail.value = '';
                shareROError.value = '';
                shareROModalOpen.value = true;
            }
            async function doShareReadOnly() {
                const email = shareROEmail.value.trim();
                if (!email) { shareROError.value = 'Enter an email address.'; return; }
                shareROSaving.value = true;
                shareROError.value = '';
                try {
                    // share_read_only reads request.data — JSON is fine.
                    const data = await apiPost(init.urls.shareReadOnly, { email });
                    shareROModalOpen.value = false;
                    toast.success(data.message || `Shared (read only) with ${email}.`);
                } catch (e) {
                    shareROError.value = e?.body?.error || e?.body?.errors?.join(' ') || e.message || 'Could not share.';
                } finally {
                    shareROSaving.value = false;
                }
            }

            // ----- Connection-info modal (SFTP / rsync / wget) -----
            const connModalOpen = ref(false);
            const connModalTitle = ref('');
            const connModalBlocks = ref([]); // [{ heading, text }]
            function showConnInfo(kind) {
                if (kind === 'sftp') {
                    connModalTitle.value = 'SFTP connection';
                    connModalBlocks.value = [
                        { heading: 'Host', text: 'sftp://' + conn.host },
                        { heading: 'Port', text: conn.sftpPort },
                        { heading: 'Username', text: conn.username + ' (same as your Bioshare login)' },
                        { heading: 'Command line', text: connStrings.sftp },
                    ];
                } else if (kind === 'rsync-download') {
                    connModalTitle.value = 'Rsync download';
                    connModalBlocks.value = [
                        { heading: 'Requires', text: 'Uploading your SSH public key first (Account → SSH Keys).' },
                        { heading: 'Download all', text: connStrings.rsyncDownload },
                    ];
                } else if (kind === 'rsync-upload') {
                    connModalTitle.value = 'Rsync upload';
                    connModalBlocks.value = [
                        { heading: 'Requires', text: 'Uploading your SSH public key first (Account → SSH Keys).' },
                        { heading: 'Upload command', text: connStrings.rsyncUpload },
                    ];
                } else if (kind === 'wget') {
                    connModalTitle.value = 'Wget download';
                    connModalBlocks.value = [
                        { heading: 'Note', text: 'Uses your current session for authentication; transfers run while you stay logged in.' },
                        { heading: 'Linux / Mac', text: connStrings.wgetLinux },
                        { heading: 'Windows (requires wget.exe)', text: connStrings.wgetWindows },
                    ];
                }
                connModalOpen.value = true;
            }

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
                canWrite, canDownload, canDelete, canLink, canEmail, canShareReadOnly,
                canAdmin, isRealpath, canCreateSubshare, subshareHref, subshareCurrentHref, unlinkDirectory,
                sftpAvailable, rsyncAvailable,
                activeTab, tabs,
                directories, files, loading, loadError, selection,
                dirHref, fileHref, onPreview,
                showUploader, onUploaded, onUploadFailed,
                moveModalOpen, moveDestination, moveError, moveSaving, openMoveModal, doMove,
                previewModalOpen, previewFile, previewContent, previewLoading,
                previewTotal, previewHasMore, loadPreviewChunk,
                folderModalOpen, folderName, folderError, folderSaving, openFolderModal, createFolder,
                renameModalOpen, renameTarget, renameTo, renameError, renameSaving, openRename, doRename,
                deleteSelected,
                metaModalOpen, metaTarget, metaNotes, metaTags, metaError, metaSaving, openMetadata, saveMetadata,
                linkModalOpen, linkName, linkTarget, linkError, linkSaving, openLinkModal, createSymlink,
                emailModalOpen, emailAllRecipients, emailSelected, emailSubject, emailBody,
                emailSending, emailError, emailRecipients, openEmailModal, sendEmail,
                shareROModalOpen, shareROEmail, shareROError, shareROSaving, openShareROModal, doShareReadOnly,
                connModalOpen, connModalTitle, connModalBlocks, showConnInfo,
                searchQuery, searchResults, searching, searched, runSearch,
                logColumns, init, fmtDateShort,
            };
        },
        template: `
            <div>
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <DropdownMenu v-if="canDownload" label="Download" variant="primary">
                        <DropdownMenuItem @select="() => window.location = init.urls.downloadZip">Zip file (up to 2 GB)</DropdownMenuItem>
                        <DropdownMenuItem v-if="sftpAvailable" @select="showConnInfo('sftp')">SFTP</DropdownMenuItem>
                        <DropdownMenuItem v-if="rsyncAvailable" @select="showConnInfo('rsync-download')">Rsync</DropdownMenuItem>
                        <DropdownMenuItem @select="showConnInfo('wget')">Wget</DropdownMenuItem>
                    </DropdownMenu>

                    <DropdownMenu v-if="canWrite" label="Upload" variant="success">
                        <DropdownMenuItem @select="showUploader = true">Browser</DropdownMenuItem>
                        <DropdownMenuItem v-if="sftpAvailable" @select="showConnInfo('sftp')">SFTP</DropdownMenuItem>
                        <DropdownMenuItem v-if="rsyncAvailable" @select="showConnInfo('rsync-upload')">Rsync</DropdownMenuItem>
                    </DropdownMenu>

                    <button v-if="canWrite" type="button" class="btn btn-success" @click="openFolderModal">
                        <span class="bi bi-folder-plus me-1" aria-hidden="true"></span>New folder
                    </button>
                    <button v-if="canLink" type="button" class="btn btn-success" @click="openLinkModal">
                        <span class="bi bi-link-45deg me-1" aria-hidden="true"></span>New link
                    </button>
                    <button v-if="canWrite" type="button" class="btn btn-success" :disabled="selection.length === 0" @click="openMoveModal">
                        <span class="bi bi-arrows-move me-1" aria-hidden="true"></span>Move<span v-if="selection.length"> ({{ selection.length }})</span>
                    </button>
                    <button v-if="canDelete" type="button" class="btn btn-danger" :disabled="selection.length === 0" @click="deleteSelected">
                        <span class="bi bi-trash me-1" aria-hidden="true"></span>Delete<span v-if="selection.length"> ({{ selection.length }})</span>
                    </button>
                    <button v-if="canEmail" type="button" class="btn btn-outline-primary" @click="openEmailModal">
                        <span class="bi bi-envelope me-1" aria-hidden="true"></span>Email
                    </button>
                    <button v-if="canShareReadOnly" type="button" class="btn btn-outline-primary" @click="openShareROModal">
                        <span class="bi bi-person-plus me-1" aria-hidden="true"></span>Share
                    </button>
                    <a v-if="canCreateSubshare" :href="subshareCurrentHref" class="btn btn-warning">
                        <span class="bi bi-share me-1" aria-hidden="true"></span>Share folder
                    </a>
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
                            :can-admin="canAdmin"
                            :can-link="canLink"
                            :is-realpath="isRealpath"
                            :dir-href="dirHref"
                            :file-href="fileHref"
                            :subshare-href="subshareHref"
                            @selection-change="sel => selection = sel"
                            @edit-metadata="openMetadata"
                            @rename="openRename"
                            @preview="onPreview"
                            @unlink="unlinkDirectory"
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

                <!-- Move modal -->
                <Modal v-model:open="moveModalOpen" title="Move selected items" size="md">
                    <form @submit.prevent="doMove">
                        <p class="text-muted small">
                            Moving {{ selection.length }} item{{ selection.length === 1 ? '' : 's' }}:
                            {{ selection.join(', ') }}
                        </p>
                        <label for="move-destination" class="form-label">Destination folder</label>
                        <input
                            id="move-destination"
                            v-model="moveDestination"
                            class="form-control"
                            :class="{ 'is-invalid': moveError }"
                            placeholder="path/relative/to/share/root"
                            autocomplete="off"
                            aria-describedby="move-destination-help"
                        />
                        <div id="move-destination-help" class="form-text">Enter a folder path relative to the share root.</div>
                        <div v-if="moveError" class="invalid-feedback d-block">{{ moveError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="moveModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="moveSaving" @click="doMove">Move</button>
                    </template>
                </Modal>

                <!-- File Preview modal -->
                <Modal v-model:open="previewModalOpen" :title="previewFile ? 'Preview: ' + previewFile.name : 'Preview'" size="xl">
                    <textarea
                        class="form-control font-monospace"
                        rows="20"
                        readonly
                        :aria-label="previewFile ? 'Contents of ' + previewFile.name : 'File contents'"
                        :value="previewContent"
                    ></textarea>
                    <template #footer>
                        <span class="me-auto small text-muted" aria-live="polite">
                            <span v-if="previewLoading">Loading…</span>
                            <span v-else-if="previewTotal != null">{{ previewTotal }} lines total</span>
                        </span>
                        <button
                            v-if="previewHasMore"
                            type="button"
                            class="btn btn-outline-secondary"
                            :disabled="previewLoading"
                            @click="loadPreviewChunk(false)"
                        >Load more</button>
                        <button type="button" class="btn btn-primary" @click="previewModalOpen = false">Close</button>
                    </template>
                </Modal>

                <!-- New Link (symlink) modal -->
                <Modal v-model:open="linkModalOpen" title="New link" size="md">
                    <form @submit.prevent="createSymlink">
                        <div class="mb-3">
                            <label for="link-name" class="form-label">Link name</label>
                            <input id="link-name" v-model="linkName" class="form-control" autocomplete="off" />
                        </div>
                        <div>
                            <label for="link-target" class="form-label">Target path</label>
                            <input id="link-target" v-model="linkTarget" class="form-control" autocomplete="off"
                                   aria-describedby="link-target-help" placeholder="/absolute/path/to/target" />
                            <div id="link-target-help" class="form-text">Absolute filesystem path the link should point to. Must be within an allowed directory.</div>
                        </div>
                        <div v-if="linkError" class="text-danger mt-2">{{ linkError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="linkModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="linkSaving" @click="createSymlink">Create link</button>
                    </template>
                </Modal>

                <!-- Email Participants modal -->
                <Modal v-model:open="emailModalOpen" title="Email participants" size="lg">
                    <form @submit.prevent="sendEmail">
                        <fieldset class="mb-3">
                            <legend class="h6">Recipients</legend>
                            <div class="form-check">
                                <input id="email-all" type="radio" class="form-check-input" :checked="emailAllRecipients" @change="emailAllRecipients = true" />
                                <label for="email-all" class="form-check-label">All participants</label>
                            </div>
                            <div class="form-check">
                                <input id="email-some" type="radio" class="form-check-input" :checked="!emailAllRecipients" @change="emailAllRecipients = false" />
                                <label for="email-some" class="form-check-label">Choose specific recipients</label>
                            </div>
                            <div v-if="!emailAllRecipients" class="ms-4 mt-1">
                                <div v-for="(addr, i) in emailRecipients" :key="i" class="form-check">
                                    <input :id="'email-r-' + i" type="checkbox" class="form-check-input" :value="addr" v-model="emailSelected" />
                                    <label :for="'email-r-' + i" class="form-check-label">{{ addr }}</label>
                                </div>
                            </div>
                        </fieldset>
                        <div class="mb-3">
                            <label for="email-subject" class="form-label">Subject</label>
                            <input id="email-subject" v-model="emailSubject" class="form-control" />
                        </div>
                        <div>
                            <label for="email-body" class="form-label">Body</label>
                            <textarea id="email-body" v-model="emailBody" class="form-control" rows="10"></textarea>
                        </div>
                        <div v-if="emailError" class="text-danger mt-2">{{ emailError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="emailModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="emailSending" @click="sendEmail">Send</button>
                    </template>
                </Modal>

                <!-- Share Read-Only modal -->
                <Modal v-model:open="shareROModalOpen" title="Share (read only)" size="md">
                    <form @submit.prevent="doShareReadOnly">
                        <p class="text-muted small">
                            Give another user read-only access to this share. If they don't have a
                            Bioshare account for the email provided, one will be created.
                        </p>
                        <label for="share-ro-email" class="form-label">Email address</label>
                        <input id="share-ro-email" v-model="shareROEmail" type="email" class="form-control"
                               :class="{ 'is-invalid': shareROError }" autocomplete="off" />
                        <div v-if="shareROError" class="invalid-feedback d-block">{{ shareROError }}</div>
                    </form>
                    <template #footer>
                        <button type="button" class="btn btn-outline-secondary" @click="shareROModalOpen = false">Cancel</button>
                        <button type="button" class="btn btn-primary" :disabled="shareROSaving" @click="doShareReadOnly">Share</button>
                    </template>
                </Modal>

                <!-- Connection-info modal (SFTP / rsync / wget) -->
                <Modal v-model:open="connModalOpen" :title="connModalTitle" size="lg">
                    <div v-for="(block, i) in connModalBlocks" :key="i" class="mb-3">
                        <h3 class="h6 mb-1">{{ block.heading }}</h3>
                        <pre class="bg-light border rounded p-2 mb-0" style="white-space: pre-wrap; word-break: break-all;">{{ block.text }}</pre>
                    </div>
                    <template #footer>
                        <button type="button" class="btn btn-primary" @click="connModalOpen = false">Close</button>
                    </template>
                </Modal>
            </div>
        `,
    }).mount(mountEl);
}
