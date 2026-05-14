// ColumnPicker.vue.js
// Fieldset + checkbox group for toggling which columns of a DataTable are
// visible. Native HTML — no Reka UI needed (it's just <fieldset> + <input
// type="checkbox"> with proper labels).
//
// Usage:
//   <ColumnPicker v-model:columns="cols" legend="Visible columns" />
//   where cols = [{ key: 'name', label: 'Name', visible: true }, ...]
//
// WAI-ARIA: fieldset + legend gives the group an accessible name. Each
// checkbox has its own <label for=id>.

import { defineComponent } from 'vue';

export const ColumnPicker = defineComponent({
    name: 'ColumnPicker',
    props: {
        columns: { type: Array, required: true },
        legend: { type: String, default: 'Visible columns' },
        legendVisible: { type: Boolean, default: true },
    },
    emits: ['update:columns'],
    setup(props, { emit }) {
        function toggle(key, visible) {
            // Mutate the reactive column directly so consumers don't need to
            // re-wire — DataTable's visibleColumns computed picks it up.
            const col = props.columns.find(c => c.key === key);
            if (col) col.visible = visible;
            // Also emit the new array form for consumers that want explicit
            // change events.
            emit('update:columns', props.columns.slice());
        }
        return { toggle };
    },
    template: `
        <fieldset class="border rounded p-2">
            <legend :class="['h6 px-2 w-auto', legendVisible ? '' : 'visually-hidden']">{{ legend }}</legend>
            <div class="d-flex flex-wrap gap-3">
                <div v-for="col in columns" :key="col.key" class="form-check m-0">
                    <input
                        :id="'colpick-' + col.key"
                        type="checkbox"
                        class="form-check-input"
                        :checked="col.visible"
                        @change="toggle(col.key, $event.target.checked)"
                    >
                    <label :for="'colpick-' + col.key" class="form-check-label">{{ col.label }}</label>
                </div>
            </div>
        </fieldset>
    `,
});
