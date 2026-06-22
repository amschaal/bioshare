// PermissionMatrix.vue.js
// The user/group permission grid for templates/share/permissions.html.
// Replaces the hand-built jQuery table + rotated-90deg column headers from
// the legacy permissions.js.
//
// Accessibility notes:
//  - Real <table> with <th scope="col"> for each permission and
//    <th scope="row"> for each principal, so AT announces "Browse permission
//    for jdoe" etc. Each checkbox also carries an explicit aria-label.
//  - Rotated text headers are gone — labels are horizontal and spelled out.
//  - "Modified" rows are not signalled by colour alone (WCAG 1.4.1): they get
//    a left border, a pencil icon, and visually-hidden "Modified" text in the
//    row header in addition to the .table-warning background.
//  - Narrow viewports: the table is wrapped in .table-responsive (Bootstrap's
//    overflow-x:auto). <table> elements are exempt from the 1.4.10 reflow
//    requirement, so a horizontally scrollable grid is conformant and far less
//    code than a parallel accordion layout.
//
// Props:
//   entries   - reactive array of row objects, each:
//               { id, kind: 'user'|'group', name, isNew, original: [perm],
//                 current: [perm] }   (this component mutates `current`)
//   readOnly  - hide the write/delete columns when the share is read-only
//   emailUsers- whether the "Send email" box is ticked (controls the envelope
//               indicator on brand-new principals)
//
// Emits:
//   remove(entry) - the row's remove button was pressed

import { defineComponent, computed } from 'vue';
import { IconButton } from '/static/js/app/components/IconButton.vue.js';

const ALL_COLUMNS = [
    { key: 'view_share_files',     label: 'Browse' },
    { key: 'download_share_files', label: 'Download' },
    { key: 'write_to_share',       label: 'Write',     writeOnly: true },
    { key: 'delete_share_files',   label: 'Delete',    writeOnly: true },
    { key: 'share_read_only',      label: 'Read-only' },
    { key: 'admin',                label: 'Admin' },
];

function sameSet(a, b) {
    if (a.length !== b.length) return false;
    const s = new Set(a);
    return b.every(x => s.has(x));
}

export const PermissionMatrix = defineComponent({
    name: 'PermissionMatrix',
    components: { IconButton },
    props: {
        entries: { type: Array, required: true },
        readOnly: { type: Boolean, default: false },
        emailUsers: { type: Boolean, default: true },
    },
    emits: ['remove'],
    setup(props, { emit }) {
        const columns = computed(() =>
            ALL_COLUMNS.filter(c => !(c.writeOnly && props.readOnly))
        );

        const isModified = (entry) => !sameSet(entry.original, entry.current);

        // A brand-new principal (no prior permissions) that has just been
        // granted something, while "Send email" is ticked, will be emailed.
        const willEmail = (entry) =>
            props.emailUsers && entry.original.length === 0 && entry.current.length > 0;

        function has(entry, key) {
            return entry.current.includes(key);
        }
        function toggle(entry, key) {
            const i = entry.current.indexOf(key);
            if (i === -1) entry.current.push(key);
            else entry.current.splice(i, 1);
        }
        function setAll(entry, on) {
            entry.current = on ? columns.value.map(c => c.key) : [];
        }

        return { columns, isModified, willEmail, has, toggle, setAll, emit };
    },
    template: `
        <div class="table-responsive">
            <table class="table table-bordered align-middle mb-0">
                <caption class="visually-hidden">
                    Permissions grid. Each row is a user or group; tick a box to grant
                    that permission. Changed rows are marked "Modified".
                </caption>
                <thead>
                    <tr>
                        <th scope="col">User or group</th>
                        <th scope="col" class="text-center" v-for="col in columns" :key="col.key">
                            {{ col.label }}
                        </th>
                        <th scope="col" class="text-center">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <tr
                        v-for="entry in entries"
                        :key="entry.kind + ':' + entry.id"
                        :class="isModified(entry) ? 'table-warning' : ''"
                        :style="isModified(entry) ? 'box-shadow: inset 4px 0 0 0 #cc8800;' : ''"
                    >
                        <th scope="row" class="fw-normal">
                            <span
                                :class="'bi me-1 ' + (entry.kind === 'group' ? 'bi-people' : 'bi-person')"
                                aria-hidden="true"
                            ></span>
                            {{ entry.name }}
                            <span v-if="isModified(entry)" class="ms-1 text-warning-emphasis">
                                <span class="bi bi-pencil-fill" aria-hidden="true"></span>
                                <span class="visually-hidden">Modified</span>
                            </span>
                            <span
                                v-if="entry.isNew"
                                class="ms-1 text-info-emphasis"
                                title="An account will be created for this email address"
                            >
                                <span class="bi bi-person-plus" aria-hidden="true"></span>
                                <span class="visually-hidden">New account will be created</span>
                            </span>
                            <span
                                v-if="willEmail(entry)"
                                class="ms-1 text-info-emphasis"
                                title="This user will be emailed about their new access"
                            >
                                <span class="bi bi-envelope" aria-hidden="true"></span>
                                <span class="visually-hidden">Will be emailed</span>
                            </span>
                        </th>
                        <td class="text-center" v-for="col in columns" :key="col.key">
                            <input
                                type="checkbox"
                                class="form-check-input"
                                :checked="has(entry, col.key)"
                                :aria-label="col.label + ' permission for ' + entry.name"
                                @change="toggle(entry, col.key)"
                            />
                        </td>
                        <td class="text-center text-nowrap">
                            <IconButton
                                icon="check-all"
                                :label="'Grant all permissions to ' + entry.name"
                                @click="setAll(entry, true)"
                            />
                            <IconButton
                                icon="x-lg"
                                :label="'Clear all permissions for ' + entry.name"
                                @click="setAll(entry, false)"
                            />
                            <IconButton
                                icon="trash"
                                variant="link"
                                :label="'Remove ' + entry.name + ' from this share'"
                                @click="emit('remove', entry)"
                            />
                        </td>
                    </tr>
                    <tr v-if="!entries.length">
                        <td :colspan="columns.length + 2" class="text-muted text-center py-3">
                            No users or groups have permissions on this share yet.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    `,
});
