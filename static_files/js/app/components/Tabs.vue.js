// Tabs.vue.js
// Thin wrapper around Reka UI Tabs parts. Arrow-key navigation,
// aria-selected/tab/tabpanel roles, focus management — all handled by Reka.
//
// Usage:
//   <Tabs v-model="activeTab" :tabs="[{ value: 'files', label: 'Files' }, ...]">
//     <template #files>...content for Files tab...</template>
//     <template #logs>...content for Logs tab...</template>
//   </Tabs>
//
// WAI-ARIA pattern: tabs.

import { defineComponent } from 'vue';
import { TabsRoot, TabsList, TabsTrigger, TabsContent } from 'reka-ui';

export const Tabs = defineComponent({
    name: 'Tabs',
    components: { TabsRoot, TabsList, TabsTrigger, TabsContent },
    props: {
        modelValue: { type: String, required: true },
        tabs: { type: Array, required: true }, // [{ value: string, label: string, disabled?: boolean }]
        orientation: { type: String, default: 'horizontal' }, // 'horizontal' | 'vertical'
        ariaLabel: { type: String, default: 'Tabs' },
    },
    emits: ['update:modelValue'],
    template: `
        <tabs-root
            :model-value="modelValue"
            :orientation="orientation"
            @update:model-value="$emit('update:modelValue', $event)"
        >
            <tabs-list
                :aria-label="ariaLabel"
                class="nav nav-tabs"
                :class="orientation === 'vertical' ? 'flex-column' : ''"
            >
                <tabs-trigger
                    v-for="tab in tabs"
                    :key="tab.value"
                    :value="tab.value"
                    :disabled="tab.disabled || false"
                    class="nav-link"
                    :class="{ active: modelValue === tab.value }"
                    style="border: 0; background: transparent;"
                >{{ tab.label }}</tabs-trigger>
            </tabs-list>
            <tabs-content
                v-for="tab in tabs"
                :key="tab.value"
                :value="tab.value"
                class="pt-3"
            ><slot :name="tab.value" /></tabs-content>
        </tabs-root>
    `,
});
