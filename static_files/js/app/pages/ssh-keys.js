// ssh-keys.js — orchestrator for ssh/list_keys.html.
// Replaces the legacy ssh_keys.js (window.confirm + jQuery $.post + manual
// row fade-out).
//
// Mount:      #ssh-keys-page-mount
// Init data:  <script id="ssh-keys-init" type="application/json">
//             { deleteUrl, keys: [{ id, name, key }] }
//
// API (unchanged):
//   POST /bioshare/api/ssh_keys/delete/  body { id }
//        -> { status:'success', deleted:<id> } | { status:'error', message }

import { createApp, ref, reactive } from 'vue';
import { apiPost } from '/static/js/app/api.js';
import { toast, announce, confirm } from '/static/js/app/state.js';
import { IconButton } from '/static/js/app/components/IconButton.vue.js';

const initEl = document.getElementById('ssh-keys-init');
const init = initEl ? JSON.parse(initEl.textContent) : {};

const mountEl = document.getElementById('ssh-keys-page-mount');
if (mountEl) {
    createApp({
        components: { IconButton },
        setup() {
            const keys = reactive([...(init.keys || [])]);
            const deletingId = ref(null);

            async function remove(entry) {
                const ok = await confirm({
                    title: 'Delete SSH key',
                    message: `Delete the SSH key "${entry.name}"? Tools that rely on it (rsync, SFTP) will lose access.`,
                    confirmLabel: 'Delete',
                    cancelLabel: 'Cancel',
                    danger: true,
                });
                if (!ok) return;

                deletingId.value = entry.id;
                try {
                    // delete_ssh_key is a plain Django view reading request.POST,
                    // so send form-encoded data rather than a JSON body.
                    const fd = new FormData();
                    fd.append('id', entry.id);
                    const data = await apiPost(init.deleteUrl, fd, { suppressErrorToast: true });
                    if (data && data.status === 'error') {
                        toast.error(data.message || 'Unable to delete SSH key.');
                        return;
                    }
                    const i = keys.findIndex(k => k.id === entry.id);
                    if (i !== -1) keys.splice(i, 1);
                    toast.success(`SSH key "${entry.name}" deleted.`);
                    announce(`SSH key ${entry.name} deleted.`);
                } catch (e) {
                    toast.error(e?.message || 'Unable to delete SSH key.');
                } finally {
                    deletingId.value = null;
                }
            }

            return { keys, deletingId, remove };
        },
        template: `
            <div>
                <table v-if="keys.length" class="table align-middle">
                    <caption class="visually-hidden">
                        Your uploaded SSH public keys. Use the delete button to remove one.
                    </caption>
                    <thead>
                        <tr>
                            <th scope="col">Name</th>
                            <th scope="col">Key</th>
                            <th scope="col" class="text-end">Delete</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="entry in keys" :key="entry.id">
                            <th scope="row" class="fw-normal text-nowrap">{{ entry.name }}</th>
                            <td>
                                <code class="small" style="word-break: break-all;">{{ entry.key }}</code>
                            </td>
                            <td class="text-end">
                                <IconButton
                                    icon="trash"
                                    :label="'Delete SSH key ' + entry.name"
                                    :disabled="deletingId === entry.id"
                                    @click="remove(entry)"
                                />
                            </td>
                        </tr>
                    </tbody>
                </table>

                <div v-else class="border rounded bg-white p-4 text-center">
                    <p class="mb-2">You have not uploaded any SSH keys yet.</p>
                    <p class="text-muted mb-0">
                        SSH keys let you upload and download files with more powerful
                        tools such as rsync. Use “Add new” above to upload one.
                    </p>
                </div>
            </div>
        `,
    }).mount(mountEl);
}
