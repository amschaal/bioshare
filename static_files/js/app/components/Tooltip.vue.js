// Tooltip.vue.js
// Accessible tooltip wrapping Reka UI Tooltip parts. Opens on pointer hover
// AND keyboard focus (so it works for keyboard-only users), dismisses on Esc.
// Reka handles all ARIA wiring (aria-describedby) automatically.
//
// Usage:
//   <Tooltip content="Delete this file permanently">
//     <button class="btn btn-icon">...</button>
//   </Tooltip>
//
// WAI-ARIA pattern: tooltip.

import { defineComponent } from 'vue';
import {
    TooltipProvider, TooltipRoot, TooltipTrigger, TooltipPortal, TooltipContent, TooltipArrow,
} from 'reka-ui';

// Self-contained: every <Tooltip> bakes in its own TooltipProvider so callers
// don't need to wrap each Vue app root. The overhead is negligible (one
// context-provider per tooltip instance).
export const Tooltip = defineComponent({
    name: 'Tooltip',
    components: { TooltipProvider, TooltipRoot, TooltipTrigger, TooltipPortal, TooltipContent, TooltipArrow },
    props: {
        content: { type: String, required: true },
        side: { type: String, default: 'top', validator: v => ['top','right','bottom','left'].includes(v) },
        sideOffset: { type: Number, default: 6 },
        delayMs: { type: Number, default: 300 },
    },
    template: `
        <TooltipProvider :delay-duration="delayMs">
            <TooltipRoot>
                <TooltipTrigger as-child>
                    <slot />
                </TooltipTrigger>
                <TooltipPortal>
                    <TooltipContent
                        :side="side"
                        :side-offset="sideOffset"
                        class="bg-dark text-white px-2 py-1 rounded small shadow"
                        style="z-index: 1080; max-width: 18rem;"
                    >
                        {{ content }}
                        <TooltipArrow class="fill-dark" :width="10" :height="5" />
                    </TooltipContent>
                </TooltipPortal>
            </TooltipRoot>
        </TooltipProvider>
    `,
});
