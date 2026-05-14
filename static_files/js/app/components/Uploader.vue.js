// Uploader.vue.js
// File upload widget. Visible <input type="file" multiple> is the primary,
// keyboard-accessible path (WCAG 2.1.1); a drag-and-drop zone is layered on
// top for pointer users but is never the only way to upload.
//
// Uses XMLHttpRequest (not fetch) because only XHR exposes upload.onprogress.
// Files upload one at a time, sequentially, so each gets its own progress bar
// — matches the legacy jquery-fileupload behaviour and the bioshare upload_file
// endpoint, which handles one POST per file.
//
// Emits:
//   uploaded(fileObject)  - per successfully uploaded file; fileObject is the
//                           server's descriptor { name, extension, size,
//                           bytes, url, modified, isText }.
//   failed(name, message) - per failed file.
//   all-done()            - when the queue drains.
//
// Replaces jquery-fileupload + jquery.iframe-transport + jquery.ui.widget.

import { defineComponent, ref, reactive } from 'vue';
import { ProgressBar } from '/static/js/app/components/ProgressBar.vue.js';

function csrfToken() {
    return (window.BIOSHARE && window.BIOSHARE.csrfToken) || '';
}

export const Uploader = defineComponent({
    name: 'Uploader',
    components: { ProgressBar },
    props: {
        url: { type: String, required: true },
        accept: { type: String, default: '' },
    },
    emits: ['uploaded', 'failed', 'all-done'],
    setup(props, { emit }) {
        const queue = ref([]);       // [reactive({ name, progress, status })]
        const uploading = ref(false);
        const dragging = ref(false);

        function uploadOne(file) {
            return new Promise((resolve) => {
                const entry = reactive({ name: file.name, progress: 0, status: 'uploading' });
                queue.value.push(entry);

                const xhr = new XMLHttpRequest();
                xhr.open('POST', props.url);
                xhr.setRequestHeader('X-CSRFToken', csrfToken());
                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) entry.progress = (e.loaded / e.total) * 100;
                };
                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        let data = {};
                        try { data = JSON.parse(xhr.responseText); } catch (_) { /* leave {} */ }
                        const serverErrors = data.errors || [];
                        const serverFiles = data.files || [];
                        if (serverErrors.length) {
                            entry.status = 'error';
                            serverErrors.forEach(msg => emit('failed', file.name, msg));
                        } else {
                            entry.progress = 100;
                            entry.status = 'done';
                        }
                        serverFiles.forEach(f => emit('uploaded', f));
                    } else {
                        entry.status = 'error';
                        emit('failed', file.name, `Upload failed (HTTP ${xhr.status})`);
                    }
                    resolve();
                };
                xhr.onerror = () => {
                    entry.status = 'error';
                    emit('failed', file.name, 'Network error during upload');
                    resolve();
                };

                const fd = new FormData();
                // The upload_file view iterates request.FILES.items(), so the
                // field name is arbitrary; 'files[]' matches the legacy markup.
                fd.append('files[]', file);
                xhr.send(fd);
            });
        }

        async function handleFiles(fileList) {
            uploading.value = true;
            for (const file of fileList) {
                await uploadOne(file);
            }
            uploading.value = false;
            emit('all-done');
        }

        function onInputChange(e) {
            const fileList = [...e.target.files];
            if (fileList.length) handleFiles(fileList);
            e.target.value = ''; // allow re-selecting the same file
        }

        function onDrop(e) {
            e.preventDefault();
            dragging.value = false;
            const fileList = [...(e.dataTransfer?.files || [])];
            if (fileList.length) handleFiles(fileList);
        }

        function clearFinished() {
            queue.value = queue.value.filter(q => q.status === 'uploading');
        }

        return { queue, uploading, dragging, onInputChange, onDrop, clearFinished };
    },
    template: `
        <div
            class="border rounded p-3"
            :class="{ 'border-primary bg-light': dragging }"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop="onDrop"
        >
            <label for="file-uploader-input" class="form-label fw-semibold">Upload files</label>
            <input
                id="file-uploader-input"
                type="file"
                multiple
                :accept="accept || undefined"
                class="form-control"
                @change="onInputChange"
            />
            <p class="text-muted small mt-1 mb-0">…or drag files onto this box.</p>

            <ul v-if="queue.length" class="list-unstyled mt-3 mb-0">
                <li v-for="(item, i) in queue" :key="i" class="mb-2">
                    <div class="d-flex justify-content-between small mb-1">
                        <span class="text-truncate" style="max-width: 70%;">{{ item.name }}</span>
                        <span v-if="item.status === 'done'" class="text-success">Done</span>
                        <span v-else-if="item.status === 'error'" class="text-danger">Failed</span>
                    </div>
                    <ProgressBar
                        :value="item.progress"
                        :label="'Upload progress for ' + item.name"
                        :variant="item.status === 'error' ? 'danger' : (item.status === 'done' ? 'success' : 'primary')"
                    />
                </li>
            </ul>
            <button
                v-if="queue.length && !uploading"
                type="button"
                class="btn btn-sm btn-link mt-1 p-0"
                @click="clearFinished"
            >Clear completed</button>
        </div>
    `,
});
