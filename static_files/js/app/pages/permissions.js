// permissions.js — orchestrator for share/permissions.html.
// Replaces the legacy permissions.js (jQuery + textcomplete + BC.ajax) and the
// hand-built permission table.
//
// Mount:      #permissions-page-mount
// Init data:  <script id="permissions-init" type="application/json">{...}</script>
//             { readOnly, secure, urls: { getPermissions, setPermissions,
//               shareWith, updateShare } }

import { createApp, ref, reactive, computed, onMounted } from 'vue';
import { apiGet, apiPost } from '/static/js/app/api.js';
import { toast, announce } from '/static/js/app/state.js';
import { PermissionMatrix } from '/static/js/app/components/PermissionMatrix.vue.js';
import { EmailAutocomplete } from '/static/js/app/components/EmailAutocomplete.vue.js';

const initEl = document.getElementById('permissions-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};
const urls = init.urls || {};

const DEFAULT_NEW_PERMS = ['view_share_files', 'download_share_files'];

// The get_permissions endpoint returns user_perms as a dict keyed by username
// (user_specific=True path) and group_perms as a list. Normalise both to the
// flat row shape PermissionMatrix expects.
function rowsFromResponse(data) {
    const rows = [];
    const userPerms = data.user_perms || {};
    const userList = Array.isArray(userPerms) ? userPerms : Object.values(userPerms);
    for (const u of userList) {
        const perms = u.permissions || [];
        rows.push({
            id: u.user.username,
            kind: 'user',
            name: u.user.username,
            isNew: false,
            original: [...perms],
            current: [...perms],
        });
    }
    for (const g of (data.group_perms || [])) {
        const perms = g.permissions || [];
        rows.push({
            id: g.group.id,
            kind: 'group',
            name: g.group.name,
            isNew: false,
            original: [...perms],
            current: [...perms],
        });
    }
    return rows;
}

function sameSet(a, b) {
    if (a.length !== b.length) return false;
    const s = new Set(a);
    return b.every(x => s.has(x));
}

const mountEl = document.getElementById('permissions-page-mount');
if (mountEl) {
    createApp({
        components: { PermissionMatrix, EmailAutocomplete },
        setup() {
            const entries = reactive([]);
            const secure = ref(!!init.secure);
            const emailUsers = ref(true);
            const loading = ref(true);
            const saving = ref(false);
            const savingGeneral = ref(false);

            const hasModified = computed(() =>
                entries.some(e => !sameSet(e.original, e.current))
            );

            function replaceEntries(rows) {
                entries.splice(0, entries.length, ...rows);
            }

            async function load() {
                loading.value = true;
                try {
                    const data = await apiGet(urls.getPermissions);
                    replaceEntries(rowsFromResponse(data));
                } catch (e) {
                    // api.js already surfaced a toast.
                } finally {
                    loading.value = false;
                }
            }

            function findEntry(kind, id) {
                return entries.find(e => e.kind === kind && String(e.id) === String(id));
            }

            function addPrincipal({ kind, id, name, isNew }) {
                if (findEntry(kind, id)) {
                    toast.info(`${name} already has a row in the grid.`);
                    return false;
                }
                entries.push({
                    id, kind, name, isNew: !!isNew,
                    original: [],
                    current: [...DEFAULT_NEW_PERMS],
                });
                return true;
            }

            async function onAddRecipient(query) {
                try {
                    const data = await apiGet(urls.shareWith, { query });
                    let added = 0;
                    for (const o of (data.exists || [])) {
                        if (addPrincipal({ kind: 'user', id: o.user.username, name: o.user.username })) added++;
                    }
                    for (const o of (data.groups || [])) {
                        if (addPrincipal({ kind: 'group', id: o.group.id, name: o.group.name })) added++;
                    }
                    for (const o of (data.new_users || [])) {
                        if (addPrincipal({ kind: 'user', id: o.user.username, name: o.user.username, isNew: true })) added++;
                    }
                    if (data.invalid && data.invalid.length) {
                        toast.error(`Invalid email(s) or unknown group(s): ${data.invalid.join(', ')}`);
                    }
                    if (data.new_users && data.new_users.length) {
                        const emails = data.new_users.map(o => o.user.username).join(', ');
                        toast.info(`An account will be created for: ${emails}`);
                    }
                    if (added) {
                        announce(`${added} ${added === 1 ? 'row' : 'rows'} added to the permissions grid. Remember to save.`);
                    }
                } catch (e) {
                    // api.js already surfaced a toast.
                }
            }

            function onRemove(entry) {
                // Clearing every permission *is* removal — save() then sends an
                // empty permission set for this principal, matching the legacy
                // "uncheck everything" behaviour.
                entry.current = [];
                announce(`Cleared all permissions for ${entry.name}. Save to apply.`);
            }

            async function save() {
                if (!hasModified.value) {
                    toast.info('No permission changes to save.');
                    return;
                }
                saving.value = true;
                const users = {};
                const groups = {};
                for (const e of entries) {
                    if (sameSet(e.original, e.current)) continue;
                    if (e.kind === 'user') users[e.id] = [...e.current];
                    else groups[e.id] = [...e.current];
                }
                try {
                    const data = await apiPost(urls.setPermissions, {
                        json: { users, groups, email: emailUsers.value },
                    });
                    replaceEntries(rowsFromResponse(data));
                    for (const m of (data.messages || [])) {
                        toast.info(m.content);
                    }
                    toast.success('Permissions have been updated.');
                    announce('Permissions saved.');
                } catch (e) {
                    // api.js already surfaced a toast.
                } finally {
                    saving.value = false;
                }
            }

            async function updateGeneral() {
                savingGeneral.value = true;
                try {
                    await apiPost(urls.updateShare, { json: { secure: secure.value } });
                    toast.success('Share settings have been updated.');
                } catch (e) {
                    // api.js already surfaced a toast.
                } finally {
                    savingGeneral.value = false;
                }
            }

            onMounted(load);

            return {
                entries, secure, emailUsers, loading, saving, savingGeneral,
                readOnly: !!init.readOnly, hasModified,
                onAddRecipient, onRemove, save, updateGeneral,
            };
        },
        template: `
            <div>
                <section class="border rounded bg-white p-3 mb-4">
                    <h2 class="h5">General settings</h2>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="secure-share" v-model="secure" />
                        <label class="form-check-label" for="secure-share">
                            Secure share
                            <span class="d-block text-muted small">
                                When unchecked, anyone with the URL may view or download files.
                            </span>
                        </label>
                    </div>
                    <button
                        type="button"
                        class="btn btn-primary btn-sm mt-2"
                        :disabled="savingGeneral"
                        @click="updateGeneral"
                    >{{ savingGeneral ? 'Updating…' : 'Update settings' }}</button>
                </section>

                <section class="border rounded bg-white p-3">
                    <h2 class="h5">Permissions</h2>

                    <div class="mb-3" style="max-width: 28rem;">
                        <label class="form-label" for="add-recipient">Add a user or group</label>
                        <EmailAutocomplete @add="onAddRecipient" />
                        <p class="form-text mb-0">
                            Pick a known address or group, or type a full email address to
                            invite a new user.
                        </p>
                    </div>

                    <div class="form-check mb-3">
                        <input class="form-check-input" type="checkbox" id="email-users" v-model="emailUsers" />
                        <label class="form-check-label" for="email-users">
                            Send email to newly added users
                            <span class="d-block text-muted small">
                                Users who already had permissions are never emailed. New
                                accounts are emailed regardless of this setting.
                            </span>
                        </label>
                    </div>

                    <p v-if="loading" class="text-muted">Loading permissions…</p>

                    <PermissionMatrix
                        v-else
                        :entries="entries"
                        :read-only="readOnly"
                        :email-users="emailUsers"
                        @remove="onRemove"
                    />

                    <button
                        type="button"
                        class="btn btn-primary mt-3"
                        :disabled="saving || !hasModified"
                        @click="save"
                    >{{ saving ? 'Updating…' : 'Update permissions' }}</button>
                    <span v-if="hasModified && !saving" class="text-warning-emphasis ms-2 small">
                        <span class="bi bi-pencil-fill" aria-hidden="true"></span>
                        You have unsaved changes.
                    </span>
                </section>
            </div>
        `,
    }).mount(mountEl);
}
