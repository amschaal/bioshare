// Accordion.vue.js
// Vertically stacked sections wrapping Reka UI Accordion parts. Used by the
// permission-matrix mobile-fallback layout (1.4.10 reflow) and elsewhere.
// Keyboard nav (Up/Down/Home/End/Space/Enter) handled by Reka.
//
// Usage:
//   <Accordion v-model="opened" :items="[{value:'a', label:'Section A'}, ...]">
//     <template #a>Content for section A</template>
//     <template #b>Content for section B</template>
//   </Accordion>
//
// `type`: 'single' (one section at a time) or 'multiple' (any number open).
// v-model is a string for type=single, an array for type=multiple.
//
// WAI-ARIA pattern: accordion.

import { defineComponent } from 'vue';
import {
    AccordionRoot, AccordionItem, AccordionHeader, AccordionTrigger, AccordionContent,
} from 'reka-ui';

export const Accordion = defineComponent({
    name: 'Accordion',
    components: { AccordionRoot, AccordionItem, AccordionHeader, AccordionTrigger, AccordionContent },
    props: {
        modelValue: { type: [String, Array], default: undefined },
        type: { type: String, default: 'single', validator: v => ['single', 'multiple'].includes(v) },
        collapsible: { type: Boolean, default: true },
        items: { type: Array, required: true }, // [{ value, label, disabled? }]
    },
    emits: ['update:modelValue'],
    template: `
        <AccordionRoot
            :model-value="modelValue"
            :type="type"
            :collapsible="collapsible"
            @update:model-value="$emit('update:modelValue', $event)"
            class="border rounded"
        >
            <AccordionItem
                v-for="(item, idx) in items"
                :key="item.value"
                :value="item.value"
                :disabled="item.disabled || false"
                :class="['accordion-item', idx > 0 ? 'border-top' : '']"
            >
                <AccordionHeader as="h3" class="m-0">
                    <AccordionTrigger
                        class="btn w-100 d-flex justify-content-between align-items-center text-start py-2 px-3 rounded-0"
                        style="border: 0; background: transparent;"
                    >
                        <span>{{ item.label }}</span>
                        <span class="bi bi-chevron-down accordion-chevron" aria-hidden="true"></span>
                    </AccordionTrigger>
                </AccordionHeader>
                <AccordionContent class="px-3 py-2 border-top">
                    <slot :name="item.value" />
                </AccordionContent>
            </AccordionItem>
        </AccordionRoot>
    `,
});
