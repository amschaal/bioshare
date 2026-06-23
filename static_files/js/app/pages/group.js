// group.js — orchestrator for groups/manage_group.html.
// Replaces the AngularJS GroupController + GroupModalInstanceCtrl + the
// $uibModal "manageGroup.html" ng-template.
//
// Mount:      #group-page-mount
// Init data:  <script id="group-init" type="application/json">
//             { groupId, groupName }
//
// API (unchanged):
//   GET  /bioshare/api/groups/<id>/            -> { id, name, users: [...] }
//   POST /bioshare/api/groups/<id>/update_users/  body { users: [{id, permissions}] }
//   GET  /bioshare/api/get_user/?query=<email> -> { user: {...} } | 404 error

import { createApp, ref, reactive, computed, onMounted } from 'vue';
import { apiGet, apiPost } from '/static/js/app/api.js';
import { toast, announce } from '/static/js/app/state.js';
import { Modal } from '/static/js/app/components/Modal.vue.js';
import { IconButton } from '/static/js/app/components/IconButton.vue.js';

const initEl = document.getElementById('group-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};
const detailUrl = `/bioshare/api/groups/${init.groupId}/`;
const updateUsersUrl = `/bioshare/api/groups/${init.groupId}/update_users/`;
const getUserUrl = '/bioshare/api/get_user/';

const mountEl = document.getElementById('group-page-mount');
if (mountEl) {
    createApp({
        components: { Modal, IconButton },
        setup() {
            const users = ref([]);          // committed group membership
            const loading = ref(true);
            const modalOpen = ref(false);
            const saving = ref(false);
            // The manage_group page view is gated by @permission_required, so
            // unauthorized users are redirected before this mounts. This covers
            // the edge case where the detail API rejects (e.g. access lost
            // mid-session) — show a clean message rather than an empty manager.
            const forbidden = ref(false);

            // Working copy while the modal is open; discarded on cancel.
            const draft = reactive([]);
            const newEmail = ref('');
            const checking = ref(false);

            const usernames = computed(() =>
                users.value.map(u => u.username).join(', ') || 'No users in this group yet.'
            );

            function applyGroup(group) {
                users.value = group.users || [];
            }

            async function load() {
                loading.value = true;
                try {
                    applyGroup(await apiGet(detailUrl, null, { suppressErrorToast: true }));
                } catch (e) {
                    if (e.response?.status === 403) forbidden.value = true;
                    else toast.error(e.message || 'Could not load this group.');
                } finally {
                    loading.value = false;
                }
            }

            function openModal() {
                // Deep-ish clone so edits don't touch the committed list and
                // each user's permissions array is independently mutable.
                draft.splice(0, draft.length, ...users.value.map(u => ({
                    id: u.id,
                    username: u.username,
                    permissions: [...(u.permissions || [])],
                })));
                newEmail.value = '';
                modalOpen.value = true;
            }

            async function addUser() {
                const email = newEmail.value.trim();
                if (!email) return;
                checking.value = true;
                try {
                    const r = await apiGet(getUserUrl, { query: email }, { suppressErrorToast: true });
                    const u = r.user;
                    if (draft.some(d => d.id === u.id)) {
                        toast.info(`${u.username} is already in this group.`);
                    } else {
                        draft.push({ id: u.id, username: u.username, permissions: [] });
                        announce(`${u.username} added. Save to apply.`);
                    }
                    newEmail.value = '';
                } catch (e) {
                    toast.error(`No user found with email or username "${email}".`);
                } finally {
                    checking.value = false;
                }
            }

            function removeUser(user) {
                const i = draft.indexOf(user);
                if (i !== -1) draft.splice(i, 1);
            }

            function isManager(user) {
                return user.permissions.includes('manage_group');
            }
            function toggleManager(user) {
                const i = user.permissions.indexOf('manage_group');
                if (i === -1) user.permissions.push('manage_group');
                else user.permissions.splice(i, 1);
            }

            async function save() {
                saving.value = true;
                try {
                    const payload = {
                        users: draft.map(u => ({ id: u.id, permissions: u.permissions })),
                    };
                    const group = await apiPost(updateUsersUrl, payload);
                    applyGroup(group);
                    modalOpen.value = false;
                    toast.success('Group membership updated.');
                    announce('Group membership saved.');
                } catch (e) {
                    // api.js already surfaced a toast.
                } finally {
                    saving.value = false;
                }
            }

            onMounted(load);

            return {
                users, usernames, loading, modalOpen, saving, forbidden,
                draft, newEmail, checking,
                groupName: init.groupName,
                openModal, addUser, removeUser, isManager, toggleManager, save,
            };
        },
        template: `
            <div v-if="forbidden" class="border rounded bg-white p-4 text-center">
                <span class="bi bi-shield-lock fs-1 text-muted d-block mb-2" aria-hidden="true"></span>
                <h2 class="h5">Access denied</h2>
                <p class="text-muted mb-0">You don't have permission to manage this group.</p>
            </div>
            <div v-else class="border rounded bg-white p-3">
                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
                    <h2 class="h5 m-0">Users</h2>
                    <button type="button" class="btn btn-sm btn-primary" @click="openModal" :disabled="loading">
                        Manage users
                    </button>
                </div>
                <p v-if="loading" class="text-muted mb-0">Loading users…</p>
                <p v-else class="mb-0">{{ usernames }}</p>

                <Modal v-model:open="modalOpen" :title="'Manage &quot;' + groupName + '&quot;'" size="lg">
                    <div class="mb-3">
                        <label class="form-label" for="add-group-user">Add a user by email or username</label>
                        <div class="input-group" style="max-width: 32rem;">
                            <input
                                id="add-group-user"
                                type="text"
                                class="form-control"
                                placeholder="user@example.com"
                                v-model="newEmail"
                                @keydown.enter.prevent="addUser"
                            />
                            <button type="button" class="btn btn-primary" @click="addUser" :disabled="checking || !newEmail.trim()">
                                {{ checking ? 'Checking…' : 'Add user' }}
                            </button>
                        </div>
                    </div>

                    <table class="table table-sm align-middle">
                        <caption class="visually-hidden">
                            Group members. Remove a user or grant them the manager role.
                        </caption>
                        <thead>
                            <tr>
                                <th scope="col">User</th>
                                <th scope="col" class="text-center">Manager</th>
                                <th scope="col" class="text-end">Remove</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="user in draft" :key="user.id">
                                <th scope="row" class="fw-normal">{{ user.username }}</th>
                                <td class="text-center">
                                    <input
                                        type="checkbox"
                                        class="form-check-input"
                                        :checked="isManager(user)"
                                        :aria-label="'Manager role for ' + user.username"
                                        @change="toggleManager(user)"
                                    />
                                </td>
                                <td class="text-end">
                                    <IconButton
                                        icon="trash"
                                        :label="'Remove ' + user.username + ' from group'"
                                        @click="removeUser(user)"
                                    />
                                </td>
                            </tr>
                            <tr v-if="!draft.length">
                                <td colspan="3" class="text-muted text-center py-3">
                                    No users in this group. Add one above.
                                </td>
                            </tr>
                        </tbody>
                    </table>

                    <template #footer>
                        <button type="button" class="btn btn-secondary" @click="modalOpen = false" :disabled="saving">
                            Cancel
                        </button>
                        <button type="button" class="btn btn-primary" @click="save" :disabled="saving">
                            {{ saving ? 'Saving…' : 'Save' }}
                        </button>
                    </template>
                </Modal>
            </div>
        `,
    }).mount(mountEl);
}
