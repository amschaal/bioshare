// MessageList.vue.js
// Loads and displays the user's active system messages (announcements from
// admins). Each message gets role="alert" so screen readers announce it,
// plus a dismiss button that POSTs to the dismiss endpoint and removes the
// message from the local list.
//
// Replaces the legacy AngularJS <message-list active> directive.
//
// Endpoints (DRF, paginated envelope {count, results}):
//   GET  /bioshare/api/messages/?active=true
//   POST /bioshare/api/messages/<id>/dismiss/
//
// Props:
//   active     - if true, only show un-dismissed messages (sidebar / top-of-page);
//                if false, show full archive (used on the messages page).
//
// WAI-ARIA: role="alert" on each item; visible dismiss button per item.

import { defineComponent, ref, onMounted } from 'vue';
import { apiGet, apiPost } from '/static/js/app/api.js';
import { IconButton } from '/static/js/app/components/IconButton.vue.js';
import { fmtDateRelative } from '/static/js/app/format.js';

export const MessageList = defineComponent({
    name: 'MessageList',
    components: { IconButton },
    props: {
        active: { type: Boolean, default: true },
    },
    setup(props) {
        const messages = ref([]);
        const loading = ref(false);
        const error = ref(null);

        async function load() {
            loading.value = true;
            error.value = null;
            try {
                const params = props.active ? { active: 'true' } : {};
                const r = await apiGet('/bioshare/api/messages/', params, { suppressServerErrorToast: true });
                messages.value = r.results || [];
            } catch (e) {
                // Don't toast a system-message fetch failure — it's a chrome-level
                // load that shouldn't disrupt the user.
                error.value = e?.message || String(e);
                messages.value = [];
            } finally {
                loading.value = false;
            }
        }

        async function dismiss(message) {
            try {
                await apiPost(`/bioshare/api/messages/${message.id}/dismiss/`);
                messages.value = messages.value.filter(m => m.id !== message.id);
            } catch (e) {
                // toast handled by api.js
            }
        }

        onMounted(load);
        return { messages, loading, dismiss, fmtDateRelative };
    },
    template: `
        <div v-if="messages.length" class="message-list mb-3">
            <div
                v-for="m in messages"
                :key="m.id"
                class="alert alert-info d-flex align-items-start gap-2"
                role="alert"
            >
                <div class="flex-grow-1">
                    <strong class="d-block">{{ m.title }}</strong>
                    <small class="text-muted" v-if="m.created">{{ fmtDateRelative(m.created) }}</small>
                    <div v-if="m.description" class="mt-1">{{ m.description }}</div>
                </div>
                <IconButton
                    icon="x-lg"
                    :label="'Dismiss ' + m.title"
                    variant="link"
                    size="sm"
                    @click="dismiss(m)"
                />
            </div>
        </div>
    `,
});
