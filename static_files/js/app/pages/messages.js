// messages.js — orchestrator for account/messages.html (the full message
// archive). Mounts the MessageList component in archive mode (active=false),
// which shows every message, not just un-dismissed ones.
//
// Mount: #message-archive-mount

import { createApp } from 'vue';
import { MessageList } from '/static/js/app/components/MessageList.vue.js';

const mountEl = document.getElementById('message-archive-mount');
if (mountEl) {
    createApp({
        components: { MessageList },
        template: `<MessageList :active="false" />`,
    }).mount(mountEl);
}
