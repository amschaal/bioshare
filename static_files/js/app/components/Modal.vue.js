// Modal.vue.js
// Modal dialog wrapping Reka UI's Dialog parts. Focus trap, focus restore on
// close, Esc-to-close, and `aria-modal="true"` are handled automatically by
// Reka UI. Slot `default` is the body; slot `footer` is optional.
//
// WAI-ARIA pattern: dialog (modal).

import { defineComponent, computed } from 'vue';
import {
    DialogRoot, DialogPortal, DialogOverlay, DialogContent,
    DialogTitle, DialogDescription, DialogClose,
} from 'reka-ui';

const SIZE_MAX_WIDTHS = {
    sm: '300px',
    md: '500px',
    lg: '800px',
    xl: '1140px',
};

export const Modal = defineComponent({
    name: 'Modal',
    components: { DialogRoot, DialogPortal, DialogOverlay, DialogContent, DialogTitle, DialogDescription, DialogClose },
    props: {
        open: { type: Boolean, required: true },
        title: { type: String, required: true },
        description: { type: String, default: '' },
        size: { type: String, default: 'md', validator: v => ['sm', 'md', 'lg', 'xl'].includes(v) },
    },
    emits: ['update:open'],
    setup(props) {
        const maxWidth = computed(() => SIZE_MAX_WIDTHS[props.size]);
        return { maxWidth };
    },
    template: `
        <dialog-root :open="open" @update:open="$emit('update:open', $event)">
            <dialog-portal>
                <dialog-overlay
                    class="position-fixed top-0 start-0 w-100 h-100 bg-dark bg-opacity-50"
                    style="z-index: 1050;"
                />
                <dialog-content
                    class="position-fixed top-50 start-50 translate-middle bg-white rounded-3 shadow-lg p-0 overflow-hidden"
                    :style="{ zIndex: 1055, width: '90vw', maxWidth, maxHeight: '90vh' }"
                >
                    <div class="d-flex flex-column" style="max-height: 90vh;">
                        <header class="d-flex align-items-center justify-content-between p-3 border-bottom">
                            <dialog-title as="h2" class="h5 m-0">{{ title }}</dialog-title>
                            <dialog-close class="btn-close" aria-label="Close" />
                        </header>
                        <div class="p-3 overflow-auto flex-grow-1">
                            <dialog-description v-if="description" class="text-muted mb-3">{{ description }}</dialog-description>
                            <slot />
                        </div>
                        <footer v-if="$slots.footer" class="p-3 border-top d-flex justify-content-end gap-2">
                            <slot name="footer" />
                        </footer>
                    </div>
                </dialog-content>
            </dialog-portal>
        </dialog-root>
    `,
});
