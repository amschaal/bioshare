// FileTable.vue.js
// Accessible file/directory listing for the share file browser. Replaces the
// jQuery DataTables instance + server-rendered <tr> rows + Handlebars row
// templates from the legacy list.html.
//
// Data is loaded by the page orchestrator (pages/list.js) from the existing
// `list_directory` view's AJAX branch (same URL + X-Requested-With header
// returns { files, directories } as JSON — no backend change).
//
// C2a scope: browsing only — render, sort, select. Row actions (rename, edit
// metadata, preview, delete, move) are wired in later C2 sub-phases; the
// action buttons render now as real <button>s (IconButton) so the markup is
// accessible, but emit events the orchestrator can ignore until then.
//
// WAI-ARIA: <table> with aria-sort on sortable <th>; row checkboxes labelled
// "Select <name>"; directory/file type conveyed by both icon + a visible
// "directory"/"file" text in a column (sr-only-friendly).

import { defineComponent, ref, computed } from 'vue';
import { IconButton } from '/static/js/app/components/IconButton.vue.js';

export const FileTable = defineComponent({
    name: 'FileTable',
    components: { IconButton },
    props: {
        directories: { type: Array, default: () => [] },
        files: { type: Array, default: () => [] },
        subdir: { type: String, default: '' },
        // Permission flags from share_perms — gate which action buttons show.
        canWrite: { type: Boolean, default: false },
        canDownload: { type: Boolean, default: false },
        // admin permission — gates the "make this folder its own share" action.
        canAdmin: { type: Boolean, default: false },
        // link_to_path capability (+ write) — gates the "unlink" action on symlinks.
        canLink: { type: Boolean, default: false },
        // false for linked/symlinked directories, where subshare/unlink are disabled.
        isRealpath: { type: Boolean, default: true },
        // (subdir, name) -> href for a directory link
        dirHref: { type: Function, required: true },
        // (name) -> href for a file download link
        fileHref: { type: Function, required: true },
        // (name) -> href to the create-subshare page for a directory
        subshareHref: { type: Function, default: null },
    },
    emits: ['edit-metadata', 'rename', 'preview', 'unlink', 'selection-change'],
    setup(props, { emit }) {
        // Sort state — null key means "natural" (directories first, then files,
        // each in load order). Sortable columns: name, extension, size, modified.
        const sortKey = ref('modified');
        const sortDir = ref('desc');

        const selected = ref(new Set());

        function toggleSort(key) {
            if (sortKey.value === key) {
                sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortKey.value = key;
                sortDir.value = 'asc';
            }
        }
        function ariaSort(key) {
            if (sortKey.value !== key) return 'none';
            return sortDir.value === 'asc' ? 'ascending' : 'descending';
        }

        function cmp(a, b, key) {
            let av, bv;
            if (key === 'size') { av = a.bytes ?? -1; bv = b.bytes ?? -1; }
            else if (key === 'modified') { av = a.mtime ?? -1; bv = b.mtime ?? -1; }
            else if (key === 'extension') { av = a.extension || ''; bv = b.extension || ''; }
            else { av = (a.name || '').toLowerCase(); bv = (b.name || '').toLowerCase(); }
            if (av < bv) return -1;
            if (av > bv) return 1;
            return 0;
        }

        // Directories always sort as a block above files (matches the legacy
        // DataTables orderFixed pre-sort on the type column).
        function sortedRows(rows) {
            if (!sortKey.value) return rows;
            const sign = sortDir.value === 'asc' ? 1 : -1;
            return [...rows].sort((a, b) => sign * cmp(a, b, sortKey.value));
        }

        const sortedDirectories = computed(() => sortedRows(props.directories));
        const sortedFiles = computed(() => sortedRows(props.files));

        const allSelectableNames = computed(() => [
            ...props.directories.map(d => d.name),
            ...props.files.map(f => f.name),
        ]);
        const allSelected = computed(() =>
            allSelectableNames.value.length > 0 &&
            allSelectableNames.value.every(n => selected.value.has(n))
        );

        function toggleRow(name, on) {
            const next = new Set(selected.value);
            if (on) next.add(name); else next.delete(name);
            selected.value = next;
            emit('selection-change', [...next]);
        }
        function toggleAll(on) {
            selected.value = on ? new Set(allSelectableNames.value) : new Set();
            emit('selection-change', [...selected.value]);
        }

        function tagNames(row) {
            const t = row.metadata?.tags;
            if (!t) return '';
            return Array.isArray(t) ? t.join(', ') : '';
        }

        return {
            sortKey, sortDir, toggleSort, ariaSort,
            sortedDirectories, sortedFiles,
            selected, allSelected, toggleRow, toggleAll, tagNames,
        };
    },
    template: `
        <table class="table table-sm table-hover align-middle" aria-label="Files and folders">
            <thead>
                <tr>
                    <th scope="col" style="width: 2.5rem;">
                        <input
                            type="checkbox"
                            class="form-check-input"
                            :checked="allSelected"
                            @change="toggleAll($event.target.checked)"
                            aria-label="Select all files and folders"
                        />
                    </th>
                    <th scope="col">Type</th>
                    <th scope="col" :aria-sort="ariaSort('name')">
                        <button type="button" class="btn btn-sm btn-link p-0 fw-semibold text-decoration-none d-inline-flex align-items-center gap-1" @click="toggleSort('name')" aria-label="Sort by name">
                            Name
                            <span v-if="ariaSort('name') === 'ascending'" class="bi bi-arrow-up" aria-hidden="true"></span>
                            <span v-else-if="ariaSort('name') === 'descending'" class="bi bi-arrow-down" aria-hidden="true"></span>
                            <span v-else class="bi bi-arrow-down-up text-muted small" aria-hidden="true"></span>
                        </button>
                    </th>
                    <th scope="col">Tags</th>
                    <th scope="col" :aria-sort="ariaSort('extension')">
                        <button type="button" class="btn btn-sm btn-link p-0 fw-semibold text-decoration-none d-inline-flex align-items-center gap-1" @click="toggleSort('extension')" aria-label="Sort by extension">
                            Extension
                            <span v-if="ariaSort('extension') === 'ascending'" class="bi bi-arrow-up" aria-hidden="true"></span>
                            <span v-else-if="ariaSort('extension') === 'descending'" class="bi bi-arrow-down" aria-hidden="true"></span>
                            <span v-else class="bi bi-arrow-down-up text-muted small" aria-hidden="true"></span>
                        </button>
                    </th>
                    <th scope="col" :aria-sort="ariaSort('size')">
                        <button type="button" class="btn btn-sm btn-link p-0 fw-semibold text-decoration-none d-inline-flex align-items-center gap-1" @click="toggleSort('size')" aria-label="Sort by size">
                            Size
                            <span v-if="ariaSort('size') === 'ascending'" class="bi bi-arrow-up" aria-hidden="true"></span>
                            <span v-else-if="ariaSort('size') === 'descending'" class="bi bi-arrow-down" aria-hidden="true"></span>
                            <span v-else class="bi bi-arrow-down-up text-muted small" aria-hidden="true"></span>
                        </button>
                    </th>
                    <th scope="col" :aria-sort="ariaSort('modified')">
                        <button type="button" class="btn btn-sm btn-link p-0 fw-semibold text-decoration-none d-inline-flex align-items-center gap-1" @click="toggleSort('modified')" aria-label="Sort by modified date">
                            Modified
                            <span v-if="ariaSort('modified') === 'ascending'" class="bi bi-arrow-up" aria-hidden="true"></span>
                            <span v-else-if="ariaSort('modified') === 'descending'" class="bi bi-arrow-down" aria-hidden="true"></span>
                            <span v-else class="bi bi-arrow-down-up text-muted small" aria-hidden="true"></span>
                        </button>
                    </th>
                    <th scope="col">Actions</th>
                </tr>
            </thead>
            <tbody>
                <tr v-if="subdir">
                    <td></td>
                    <td>directory</td>
                    <td><span class="bi bi-folder me-1" aria-hidden="true"></span><a href="../">../</a></td>
                    <td></td><td></td><td></td><td></td><td></td>
                </tr>

                <tr v-for="dir in sortedDirectories" :key="'d-' + dir.name">
                    <td>
                        <input type="checkbox" class="form-check-input"
                            :checked="selected.has(dir.name)"
                            @change="toggleRow(dir.name, $event.target.checked)"
                            :aria-label="'Select ' + dir.name" />
                    </td>
                    <td>directory</td>
                    <td>
                        <span :class="dir.target ? 'bi bi-folder-symlink' : 'bi bi-folder'" class="me-1" aria-hidden="true"></span>
                        <a :href="dirHref(subdir, dir.name)">{{ dir.name }}</a>
                    </td>
                    <td>{{ tagNames(dir) }}</td>
                    <td></td>
                    <td></td>
                    <td>{{ dir.modified }}</td>
                    <td>
                        <span class="d-inline-flex gap-1 align-items-center">
                            <IconButton v-if="canWrite" icon="tag" label="Edit metadata" variant="link" size="sm" @click="$emit('edit-metadata', { type: 'directory', row: dir })" />
                            <IconButton v-if="canWrite" icon="pencil" label="Rename" variant="link" size="sm" @click="$emit('rename', { type: 'directory', row: dir })" />
                            <a v-if="dir.share" :href="dir.share.url" class="btn btn-link btn-sm" :aria-label="'Shared as &quot;' + dir.share.name + '&quot;'" :title="'Shared as &quot;' + dir.share.name + '&quot;'">
                                <span class="bi bi-people" aria-hidden="true"></span>
                            </a>
                            <a v-else-if="canAdmin && !dir.target && isRealpath && subshareHref" :href="subshareHref(dir.name)" class="btn btn-link btn-sm" aria-label="Make this folder its own share" title="Make this folder its own share">
                                <span class="bi bi-share" aria-hidden="true"></span>
                            </a>
                            <IconButton v-if="canAdmin && dir.target && canLink && isRealpath" icon="x-circle" label="Unlink this directory" variant="link" size="sm" @click="$emit('unlink', dir)" />
                        </span>
                    </td>
                </tr>

                <tr v-for="file in sortedFiles" :key="'f-' + file.name">
                    <td>
                        <input type="checkbox" class="form-check-input"
                            :checked="selected.has(file.name)"
                            @change="toggleRow(file.name, $event.target.checked)"
                            :aria-label="'Select ' + file.name" />
                    </td>
                    <td>file</td>
                    <td>
                        <span v-if="file.target" class="bi bi-link-45deg me-1" aria-hidden="true"></span>
                        <span class="bi bi-file-earmark me-1" aria-hidden="true"></span>
                        <a v-if="canDownload" :href="fileHref(file.name)">{{ file.name }}</a>
                        <span v-else>{{ file.name }}</span>
                    </td>
                    <td>{{ tagNames(file) }}</td>
                    <td>{{ file.extension || '' }}</td>
                    <td>{{ file.size }}</td>
                    <td>{{ file.modified }}</td>
                    <td>
                        <span class="d-inline-flex gap-1">
                            <IconButton v-if="canWrite" icon="tag" label="Edit metadata" variant="link" size="sm" @click="$emit('edit-metadata', { type: 'file', row: file })" />
                            <IconButton v-if="canDownload && file.isText" icon="eye" label="Preview file contents" variant="link" size="sm" @click="$emit('preview', file)" />
                            <IconButton v-if="canWrite" icon="pencil" label="Rename" variant="link" size="sm" @click="$emit('rename', { type: 'file', row: file })" />
                        </span>
                    </td>
                </tr>

                <tr v-if="sortedDirectories.length === 0 && sortedFiles.length === 0 && !subdir">
                    <td colspan="8" class="text-center text-muted py-3">This share is empty.</td>
                </tr>
            </tbody>
        </table>
    `,
});
