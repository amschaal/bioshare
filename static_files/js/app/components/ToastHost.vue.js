// ToastHost.vue.js
// Renders one Toast per entry in state.toasts. Positioned by the .toast-host
// class in components.css. Errors get role="alert" + aria-live="assertive"
// (interrupting), other kinds get role="status" + aria-live="polite".

import { defineComponent } from 'vue';
import { state, dismissToast } from '/static/js/app/state.js';

const ICON_BY_KIND = {
    info: 'info-circle',
    success: 'check-circle',
    warning: 'exclamation-triangle',
    error: 'x-octagon',
};

const BS_BG_BY_KIND = {
    info: 'text-bg-info',
    success: 'text-bg-success',
    warning: 'text-bg-warning',
    error: 'text-bg-danger',
};

export const ToastHost = defineComponent({
    name: 'ToastHost',
    setup() {
        return { state, dismissToast, ICON_BY_KIND, BS_BG_BY_KIND };
    },
    template: `
        <div class="toast-host">
            <div
                v-for="t in state.toasts"
                :key="t.id"
                :class="['toast', 'show', 'border-0', BS_BG_BY_KIND[t.kind] || 'text-bg-info']"
                :role="t.kind === 'error' ? 'alert' : 'status'"
                :aria-live="t.kind === 'error' ? 'assertive' : 'polite'"
                aria-atomic="true"
            >
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center gap-2">
                        <span :class="'bi bi-' + (ICON_BY_KIND[t.kind] || 'info-circle')" aria-hidden="true"></span>
                        <span>{{ t.message }}</span>
                    </div>
                    <button
                        type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        :aria-label="'Dismiss notification'"
                        @click="dismissToast(t.id)"
                    ></button>
                </div>
            </div>
        </div>
    `,
});
