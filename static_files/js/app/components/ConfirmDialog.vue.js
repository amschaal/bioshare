// ConfirmDialog.vue.js
// Confirmation dialog wrapping Reka UI's AlertDialog parts. role="alertdialog",
// focus trap, focus restore. Replaces every window.confirm() call site.
//
// Imperative API: page code calls `confirm({ title, message, confirmLabel, ... })`
// from state.js, which returns a Promise<boolean>. A single global ConfirmDialog
// (mounted via main.js) reads from state.confirm and resolves the promise on
// the user's choice.
//
// Internal coordination: AlertDialogAction and AlertDialogCancel buttons
// AUTO-CLOSE the dialog via Reka's internal click handler, which fires before
// our @click handler. We can't rely on @click ordering. Instead, capture-phase
// listeners flip a `pendingResult` flag before Reka's close runs, and
// onOpenChange reads that flag to decide what to resolve with.
//
// WAI-ARIA pattern: alertdialog.

import { defineComponent, computed } from 'vue';
import {
    AlertDialogRoot, AlertDialogPortal, AlertDialogOverlay, AlertDialogContent,
    AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel,
} from 'reka-ui';
import { state } from '/static/js/app/state.js';

export const ConfirmDialog = defineComponent({
    name: 'ConfirmDialog',
    components: {
        AlertDialogRoot, AlertDialogPortal, AlertDialogOverlay, AlertDialogContent,
        AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel,
    },
    setup() {
        const isOpen = computed(() => state.confirm !== null);
        // null until user clicks Yes/No; Esc / outside-click bypasses these handlers
        // and falls through to onOpenChange with pendingResult still null (treated as cancel).
        let pendingResult = null;

        function onConfirmClick() { pendingResult = true; }
        function onCancelClick() { pendingResult = false; }

        function onOpenChange(open) {
            if (!open && state.confirm) {
                const value = pendingResult === true; // null/false both => cancelled
                pendingResult = null;
                state.confirm.resolve(value);
                state.confirm = null;
            }
        }

        return { state, isOpen, onConfirmClick, onCancelClick, onOpenChange };
    },
    template: `
        <AlertDialogRoot :open="isOpen" @update:open="onOpenChange">
            <AlertDialogPortal>
                <AlertDialogOverlay
                    class="position-fixed top-0 start-0 w-100 h-100 bg-dark bg-opacity-50"
                    style="z-index: 1060;"
                />
                <AlertDialogContent
                    v-if="state.confirm"
                    class="position-fixed top-50 start-50 translate-middle bg-white rounded-3 shadow-lg p-0 overflow-hidden"
                    style="z-index: 1065; width: 90vw; max-width: 480px;"
                >
                    <div class="p-3">
                        <AlertDialogTitle as="h2" class="h5 mb-2">{{ state.confirm.title }}</AlertDialogTitle>
                        <AlertDialogDescription class="m-0">{{ state.confirm.message }}</AlertDialogDescription>
                    </div>
                    <div class="p-3 pt-0 d-flex justify-content-end gap-2">
                        <AlertDialogCancel
                            class="btn btn-sm btn-outline-secondary"
                            @click.capture="onCancelClick"
                        >{{ state.confirm.cancelLabel || 'Cancel' }}</AlertDialogCancel>
                        <AlertDialogAction
                            :class="['btn', 'btn-sm', state.confirm.danger ? 'btn-danger' : 'btn-primary']"
                            @click.capture="onConfirmClick"
                        >{{ state.confirm.confirmLabel || 'OK' }}</AlertDialogAction>
                    </div>
                </AlertDialogContent>
            </AlertDialogPortal>
        </AlertDialogRoot>
    `,
});
