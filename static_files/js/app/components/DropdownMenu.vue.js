// DropdownMenu.vue.js
// Trigger + menu pattern wrapping Reka UI's DropdownMenu parts. Keyboard
// navigation (Up/Down/Home/End/letter-jump), Esc-to-close, focus management,
// aria-haspopup="menu" are all handled by Reka UI.
//
// Usage:
//   <DropdownMenu label="Actions">
//     <DropdownMenuItem @select="onDelete">Delete</DropdownMenuItem>
//     <DropdownMenuItem disabled>Archive</DropdownMenuItem>
//   </DropdownMenu>
//
// WAI-ARIA pattern: menu.

import { defineComponent } from 'vue';
import {
    DropdownMenuRoot, DropdownMenuTrigger, DropdownMenuPortal,
    DropdownMenuContent, DropdownMenuItem as RekaDropdownMenuItem,
    DropdownMenuSeparator,
} from 'reka-ui';

export const DropdownMenu = defineComponent({
    name: 'DropdownMenu',
    components: { DropdownMenuRoot, DropdownMenuTrigger, DropdownMenuPortal, DropdownMenuContent },
    props: {
        label: { type: String, required: true },        // accessible name + visible text
        variant: { type: String, default: 'secondary' }, // bootstrap btn-* variant
        align: { type: String, default: 'start' },       // 'start' | 'end' for menu alignment
    },
    template: `
        <dropdown-menu-root :modal="false">
            <dropdown-menu-trigger :class="['btn', 'btn-sm', 'btn-' + variant]">
                {{ label }}
                <span class="bi bi-caret-down-fill ms-1 small" aria-hidden="true"></span>
            </dropdown-menu-trigger>
            <dropdown-menu-portal>
                <dropdown-menu-content
                    class="bg-white rounded-2 shadow border py-1"
                    :align="align"
                    :side-offset="4"
                    style="z-index: 1070; min-width: 10rem;"
                >
                    <slot />
                </dropdown-menu-content>
            </dropdown-menu-portal>
        </dropdown-menu-root>
    `,
});

// Re-export the Reka UI parts our consumers will use directly.
export const DropdownMenuItem = defineComponent({
    name: 'DropdownMenuItem',
    components: { RekaDropdownMenuItem },
    props: {
        disabled: { type: Boolean, default: false },
        danger: { type: Boolean, default: false },
    },
    emits: ['select'],
    template: `
        <reka-dropdown-menu-item
            :disabled="disabled"
            :class="[
                'px-3 py-2 d-block text-decoration-none',
                'cursor-pointer',
                disabled ? 'text-muted' : (danger ? 'text-danger' : 'text-body'),
                'rounded-0',
            ]"
            style="user-select: none;"
            @select="$emit('select', $event)"
        ><slot /></reka-dropdown-menu-item>
    `,
});

export { DropdownMenuSeparator };
