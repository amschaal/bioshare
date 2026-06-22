# BioShareX frontend revamp — Bootstrap 5 + Vue 3 (MVC mode)

## Context

The current frontend stack is a stack of unmaintained libraries that actively fights WCAG 2.1 AA compliance: Bootstrap 2 (2012, EOL), jQuery 1.10.1 (2013), AngularJS 1.x (Google LTS ended Dec 2021), Handlebars client-side templates, DataTables jQuery, Dynatree, jQuery File Upload. Bolting accessibility patches onto this stack — as the in-flight `django5-upgrade` branch is attempting — produces bug-prone changes for diminishing return.

This plan replaces the frontend stack with **Bootstrap 5 (CSS only) + Vue 3 (vanilla ES modules via import map, no runtime build step) + Reka UI (vendored single-ESM bundle) for ARIA-correct interactive widgets**. Vue runs in MVC mode: mounted on Django-rendered nodes, no router, no SPA. The Django views, the DRF API, and all backend logic are **unchanged**. JSON endpoint response shapes stay JSON. The change is purely a frontend re-platform on a fresh branch (`frontend-revamp`) cut from `django5-upgrade`, so the Django 5 upgrade ships together with the new accessible frontend. Reverting is `git checkout django5-upgrade`. The in-flight accessibility patches currently on `django5-upgrade` (the `a11y_handler` wrapper, ARIA additions in [main.js](static_files/js/share/main.js) / [permissions.js](static_files/js/share/permissions.js), BS3-compat shims in [bioshare.css](static_files/css/bioshare.css)) are superseded automatically — every file containing them is either deleted or rewritten by this plan, so the patches go away without explicit revert.

Goal: every screen reaches WCAG 2.1 AA — every custom widget mapped to a named WAI-ARIA Authoring Practices pattern, focus management, contrast, keyboard operation, live-region announcements, and 200%-zoom / 320px-reflow handled deliberately rather than retrofitted.

## Decisions locked

- Branch: `frontend-revamp` off `django5-upgrade` — ships Django 5 + accessible frontend as one merge
- Vue 3.5.x ESM browser build (`vue.esm-browser.prod.js`) — no Vite/npm/package.json at runtime; modules resolve via a `<script type="importmap">` block emitted from `base.html`
- Reka UI 2.9.x — chosen over Headless UI Vue for: larger APG-conformant component surface (Accordion, Tooltip, Slider, Toggle Group, Navigation Menu, Hover Card, Context Menu — components Headless UI doesn't ship), CSS-agnostic docs (data-attribute styling via `[data-state]`, `[data-disabled]` rather than Tailwind-only examples), and `https://reka-ui.com/llms.txt` provides canonical per-component markdown for current API references via WebFetch during implementation. Distributed as a single `reka-ui.bundle.esm.js` produced one-time by `esbuild --bundle --format=esm --external:vue` during vendoring (Vue resolved at runtime via importmap); transitive deps (`@floating-ui/vue`, `@vueuse/core`, `@tanstack/vue-virtual`, etc.) are inlined into the bundle so the deployed runtime is just the one file.
- Bootstrap 5.3.3 CSS only — no Bootstrap JS (its DOM manipulation conflicts with Vue's virtual DOM, and Reka UI handles all interactivity)
- Bootstrap Icons 1.11 replaces famfamfam-bootstrap; legacy `fam-*` class names aliased via [static_files/css/legacy-icon-shim.css](static_files/css/legacy-icon-shim.css) during migration, removed at end
- All-at-once migration on the branch before any merge — full revamp before review
- Keep current visual look (priority: accessibility, not redesign)
- Dynatree removed — move-to dialog uses a simple `<PathPicker>` text input; `<TreePicker>` is a stretch goal
- DataTables (jQuery) and ng-table replaced with one custom `<DataTable>` Vue component
- Drag-and-drop file upload is a stretch goal; the visible `<input type="file" multiple>` is the keyboard-accessible primary path
- axe-core 4.10.x served via CDN-style vendored static file, runs in DEBUG only, logs to console

## Prerequisite: Playwright MCP available in the dev container

This plan assumes Playwright MCP is reachable from Claude Code in the devcontainer so I can navigate pages, run axe-core in-page, take screenshots, exercise keyboard interactions, and confirm JSON request/response shapes per page during development. Setup is handled separately by the developer (rough recipe: add `npx playwright install-deps chromium` + `npx playwright install chromium` to [.devcontainer/Dockerfile](.devcontainer/Dockerfile), add `.mcp.json` at project root pointing at `@playwright/mcp@latest --headless --browser chromium --isolated`, whitelist `playwright.download.prss.microsoft.com` and `cdn.playwright.dev` in [.devcontainer/init-firewall.sh](.devcontainer/init-firewall.sh) if it restricts egress, rebuild devcontainer).

Operational facts:
- App URL from inside the devcontainer is `http://bioshare:9999` (docker DNS on `bioshare_internal-network`), **not** `http://localhost:9000`.
- Headless only — no live browser window; screenshots returned as files.
- A dedicated dev login (test user) is needed before browser testing starts, since most screens require auth.

What Playwright covers vs. what still requires a human:
- **Playwright (me):** rendering, click/type/submit flows, focus order, focus traps, focus return on modal close, keyboard navigation (Tab, Shift+Tab, Enter, Space, Esc, arrows), JSON request/response shapes in the network panel, axe-core per page, screenshots for visual comparison, 320px viewport reflow, prefers-reduced-motion.
- **Human (you):** NVDA / VoiceOver screen-reader passes, subjective "is the focus ring obvious enough," cross-browser quirks beyond Chromium.

If Playwright setup fails or is skipped, fall back to the manual workflow described in the original Verification section (you run the dev server, watch the axe console output, report regressions).

## The single backend touch (everything else is frontend)

[requirements.txt](requirements.txt): swap `crispy-bootstrap3` → `crispy-bootstrap5>=2024.10`.

[settings/settings.py](settings/settings.py) — three lines (lines ~146, ~216–217):
- `INSTALLED_APPS`: `'crispy_bootstrap3'` → `'crispy_bootstrap5'`
- `CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'`
- `CRISPY_TEMPLATE_PACK = 'bootstrap5'`

No views, forms, models, serializers, URLs, or any other Python touched.

## New file layout

```
static_files/lib/
  vue/            vue.esm-browser.prod.js, vue.esm-browser.js (dev)
  reka-ui/        reka-ui.bundle.esm.js  (single ESM, all transitive deps inlined; vue external)
  bootstrap5/     css/bootstrap.min.css(.map)
  bootstrap-icons/ bootstrap-icons.min.css + fonts/
  axe-core/       axe.min.js (dev only)

static_files/css/
  bioshare.css           (rewritten — Bootstrap 5 idioms, drop BS3-shim block)
  components.css         (NEW — focus rings, dialog z-index, reduced-motion, skip-link)
  legacy-icon-shim.css   (NEW — fam-* / icon-* aliases to bi-*; deleted at end)

static_files/js/app/
  main.js                (bootstrap, singletons mount)
  api.js                 (fetch wrapper + CSRF + 401/429 routing; replaces BC.ajax + csrf.js + lib.js)
  state.js               (Vue reactive() store: toasts, announce, current user)
  url-state.js           (replaces LocationSearchState; preserves existing ?tableSettings.* bookmark format)
  format.js              (fmtDateShort, fmtBytes)
  components/            (~25 component files — see §"Components" below)
  pages/                 (per-page orchestrators: list.js, permissions.js, shares.js, share-detail.js, groups.js, group.js, ssh-keys.js, log-table.js, search.js)
```

Components are `.vue.js` files exporting plain objects with backtick `template:` strings. Vue's `compile()` runs at runtime since `vue.esm-browser.prod.js` is the **full** browser ESM build (includes the runtime compiler), not the `.runtime` variant.

## Components (with ARIA pattern + JSON shape)

Replaces all of [main.js](static_files/js/share/main.js), [permissions.js](static_files/js/share/permissions.js), [bioshare.js](static_files/js/bioshare.js), [lib.js](static_files/js/lib.js), [csrf.js](static_files/js/csrf.js), all Angular controllers, message-directives, Handlebars templates.

| Component | WAI-ARIA pattern | Consumes / Replaces |
|---|---|---|
| `<Modal>` | dialog (modal) — focus trap, restore on close | Bootstrap 2 `.modal` (12 instances) |
| `<ConfirmDialog>` | alertdialog | every `window.confirm()` (delete, unlink, move, ssh-key delete) |
| `<Toast>` / `<ToastHost>` | status / alert + polite/assertive live region | `$.bootstrapGrowl` |
| `<Announce>` | live region (singleton) | scattered ad-hoc `aria-live` divs |
| `<DropdownMenu>` | menu — roving tabindex, Esc + arrows | Bootstrap 2 `dropdown-toggle` |
| `<Tabs>` (wraps Reka UI `TabsRoot`/`TabsList`/`TabsTrigger`/`TabsContent`) | tabs | `nav-tabs` in [list.html](templates/list.html) |
| `<Combobox>` (wraps Reka UI `ComboboxRoot`/`ComboboxAnchor`/`ComboboxInput`/`ComboboxContent`/`ComboboxItem`) | combobox + listbox | bootstrap-typeahead, jquery-textcomplete |
| `<Tooltip>` (wraps Reka UI `TooltipRoot`/`TooltipTrigger`/`TooltipContent`) | tooltip — keyboard + hover trigger, automatic ARIA wiring | manual `[title]` attributes site-wide |
| `<Accordion>` (wraps Reka UI `AccordionRoot`/`AccordionItem`/`AccordionTrigger`/`AccordionContent`) | accordion | needed for `<PermissionMatrix>` mobile-width fallback layout (1.4.10) |
| `<ShareAutocomplete>` | uses Combobox; `GET /api/share_autocomplete/?query=` | sidebar typeahead in [base.html](templates/base.html) |
| `<EmailAutocomplete>` | Combobox; `GET /api/get_addresses/?q=` → `{emails, groups}` | textcomplete in [permissions.js:227-271](static_files/js/share/permissions.js#L227-L271) |
| `<DataTable>` | `<table>` with `aria-sort`, filter inputs with labels, pagination as `<nav>` | DataTables jQuery + all 4 ng-table instances |
| `<Pagination>` | navigation with `aria-current="page"` | DataTables / ng-table pagination |
| `<ColumnPicker>` | `<fieldset><legend>` + checkbox group | col-toggle in [shares.html](templates/share/shares.html) |
| `<FileTable>` + `<FileRow>` / `<DirectoryRow>` | `<table>` with row checkboxes labelled `Select <name>`; action cells use `<IconButton>` | DataTables + Handlebars row builders + main.js wiring in [list.html](templates/list.html) and [handlebars/list_files.html](templates/handlebars/list_files.html) |
| `<IconButton>` | real `<button>` with `aria-label`, icon inside `<span aria-hidden="true">` | every `<i role="button" tabindex="0">` and `<a href="#">` action site-wide |
| `<TagChip>` | `<button aria-pressed>` | `<span class="tag">` from Handlebars `list_tags` helper |
| `<PermissionMatrix>` + `<PermissionRow>` | table with `scope="row"`; rotated 90° headers replaced with horizontal abbreviated labels + tooltip; below 640px becomes accordion of cards (one per user/group) | [permissions.html](templates/share/permissions.html) + [permissions.js](static_files/js/share/permissions.js) |
| `<Uploader>` + `<ProgressBar>` | visible `<input type=file>`; `role="progressbar"` with `aria-valuenow/min/max`; XHR for progress | jquery-fileupload + iframe-transport + ui.widget |
| `<MessageList>` | `role="alert"` per active item + dismiss button | AngularJS `message-list` directive ([message-directives.js](static_files/js/directives/message-directives.js)) |
| `<SidebarShares>` | `<nav aria-label>` + `<ul>` | currently server-rendered cached block in [base.html:103-128](templates/base.html#L103-L128) — keep cache, emit JSON via `{{ data|json_script:"sidebar-data" }}`, mount Vue on it |
| `<FilePreview>` | dialog + `aria-live` line counter | [dialogs/preview_file.html](templates/dialogs/preview_file.html) + preview code in [bioshare.js](static_files/js/bioshare.js) |
| `<MetadataEditor>` | dialog with form | `#edit-metadata` modal + metadata code in [main.js:161-238](static_files/js/share/main.js#L161-L238) |
| `<PathPicker>` | textbox with `aria-describedby` example | dynatree in move modal |
| `<TreePicker>` (optional) | tree pattern — `treeitem`, `group`, `aria-expanded`, `aria-selected`, arrow + Home/End | dynatree replacement, if pursued |

## JSON endpoint shapes consumed (unchanged from current API)

- `GET /api/share_autocomplete/?query=` → `{shares: [{name, notes, url}], errors?}`
- `GET /api/get_addresses/?q=` → `{emails, groups}`
- `GET /api/get_permissions/<share>/` → `{user_perms: [{user, permissions}], group_perms: [{group, permissions}]}`
- `POST /api/set_permissions/<share>/` body: `{users, groups, email}`
- `POST .../create_folder/`, `.../create_symlink/` → `{objects: [{name, type, metadata, modified, display?}]}`
- `POST .../move_paths/` → `{moved, failed}` ; `.../delete_paths/` → `{deleted, failed}`
- `GET /api/search/<share>/?query=` → `{results: [paths]}`
- `POST /api/edit_metadata/<share>/<subpath>/` → `{name, tags, notes}`
- `GET /api/md5sum/<share>/<path>/` → `{md5sum}`
- `GET /api/get_directories/<share>/?directory=` → tree node list (only consumed if `<TreePicker>` is built)
- `GET /api/shares/` (DRF, paginated) → `{count, next, previous, results}`
- `GET /api/logs/` (DRF, paginated) — same envelope
- `GET /api/messages/?active=true` — same envelope; `POST /api/messages/<id>/dismiss/`

## Per-screen migration

Implementation order matches the phases below.

| # | Template | Replaces | Components used | WCAG criteria | Size |
|---|---|---|---|---|---|
| 1 | [base.html](templates/base.html) | jquery, angular stack, BS2 JS, growl, handlebars, dynatree CSS, ng-table CSS, jsurls, csrf.js, lib.js, bioshare.js, models.js, message-directives | DropdownMenu, ShareAutocomplete, MessageList, ToastHost, Announce, ConfirmDialog (singleton), SidebarShares | 1.3.1, 1.4.10, 2.1.1, 2.4.1, 2.4.3, 4.1.2, 4.1.3 | M |
| 2 | [share/shares.html](templates/share/shares.html) | shares-controller.js, ng-table-services.js, ng-page-state.js, LocationSearchState | DataTable, ColumnPicker, TagChip, Combobox, Pagination | 1.3.1, 1.4.10, 2.4.3, 4.1.2, 4.1.3 | L |
| 3 | [share/logs.html](templates/share/logs.html) | ng-table LogController | DataTable | 1.3.1, 4.1.2 | S |
| 4 | [list.html](templates/list.html) | main.js, SizeController, handlebars/list_files.html, jquery-fileupload, dynatree, DataTables, BC.* helpers, 7 inline modals | Tabs, FileTable, FileRow, DirectoryRow, IconButton, TagChip, DropdownMenu, Modal×7, ConfirmDialog, MetadataEditor, Uploader, ProgressBar, FilePreview, PathPicker | 1.1.1, 1.3.1, 1.3.4, 1.4.1, 2.1.1, 2.1.2, 2.4.3, 2.4.7, 3.3.1, 4.1.2, 4.1.3 | L |
| 5 | [share/permissions.html](templates/share/permissions.html) | permissions.js, jquery-textcomplete, dynamic row builder, rotated-text headers | PermissionMatrix, PermissionRow, EmailAutocomplete, IconButton | 1.3.1 (headers), 1.4.1 (color-only "modified" → border + icon + color), 1.4.10 (matrix → accordion below 640px), 2.1.1, 4.1.2 | L |
| 6 | [groups/groups.html](templates/groups/groups.html) | groups-controller.js, ng-table | DataTable, Combobox | 1.3.1, 4.1.2 | S |
| 7 | [groups/manage_group.html](templates/groups/manage_group.html) | group-controller.js, ng-table, $uibModal | DataTable, Modal, EmailAutocomplete | 1.3.1, 2.1.1, 2.4.3, 4.1.2 | M |
| 8 | [groups/create_modify_group.html](templates/groups/create_modify_group.html) | (none beyond base) | (pure crispy-bootstrap5) | label/error semantics from crispy | S |
| 9 | [ssh/list_keys.html](templates/ssh/list_keys.html) | ssh_keys.js | IconButton, ConfirmDialog, Toast | 2.1.1, 4.1.2 | S |
| 10 | [ssh/new_key.html](templates/ssh/new_key.html) | (none) | (crispy only) | crispy | S |
| 11 | [share/edit_share.html](templates/share/edit_share.html), [new_share.html](templates/share/new_share.html), [new_form.html](templates/share/new_form.html), [delete_share.html](templates/share/delete_share.html) | (none) | ConfirmDialog (delete only) | crispy + delete confirm | S |
| 12 | [share/links.html](templates/share/links.html) | DataTables jquery | DataTable | 1.3.1, 4.1.2 | S |
| 13 | [dialogs/preview_file.html](templates/dialogs/preview_file.html) | jquery modal + scroll handler, bioshare.js preview | Modal, FilePreview | 1.3.1, 2.1.2, 2.4.3, 4.1.3 | M |
| 14 | [dialogs/email_users.html](templates/dialogs/email_users.html) | inline jquery, BC.ajax_form_submit | Modal, native form, Toast | 1.3.1, 2.4.3, 3.3.1 | S |
| 15 | [dialogs/share_read_only.html](templates/dialogs/share_read_only.html) | inline jquery | Modal, native form, Toast | 1.3.1, 2.4.3 | S |
| 16 | [search/search_files.html](templates/search/search_files.html) | DataTables jquery | DataTable (client-side) | 1.3.1, 4.1.2 | S |
| 17 | [account/messages.html](templates/account/messages.html) | message-list directive | MessageList (full mode) | same as base | S |
| 18 | [handlebars/list_files.html](templates/handlebars/list_files.html) | (deleted entirely) | — | n/a | S |
| 19 | error pages, [index.html](templates/index.html) | (none) | (none) | crispy + new focus rings | S each |
| 20 | [registration/*](templates/registration/) (~14 templates) | (none) | (none) | crispy + bs5 form classes | S each |
| 21 | [viz/cloud.html](templates/viz/cloud.html) | (none — keep d3) | (add `role="img"` + `<title>` to SVG) | 1.1.1 | S |
| 22 | [wget_listing.html](templates/wget_listing.html) | (leave — raw HTML for wget consumers) | — | — | S |

## Phased build order (within the single branch)

**Phase 0 — Persist this plan to the repo.** The plan was initially copied to `/workspace/frontend_revamp_plan.md` on the `frontend-revamp` branch (uncommitted). Before any code change, refresh that file so it includes the latest revisions (Playwright prerequisite, updated Verification section). The plan in `~/.claude/plans/` is scratch; the project-root copy is the durable artifact.

**Phase A — Foundation.** Branch off `django5-upgrade`. Vendor [lib/vue, lib/reka-ui, lib/bootstrap5, lib/bootstrap-icons, lib/axe-core](static_files/lib/). Backend touch (crispy swap). New `components.css`, `legacy-icon-shim.css`, rewritten `bioshare.css`. Build every shared primitive (Modal, ConfirmDialog, Toast/ToastHost, Announce, IconButton, DropdownMenu, Combobox, Tabs, Tooltip, Accordion, Pagination, DataTable, ColumnPicker). Per-component dev fixture HTMLs in `static_files/dev/` for axe + manual verification (not collected; gitignored or kept out of `STATICFILES_DIRS`).

**Phase B — Shell.** Rewrite [base.html](templates/base.html). Wire `pages/base.js` to mount sidebar autocomplete, dropdown menus, message list, toast host, announce, confirm dialog singleton. Every child template inherits the new chrome.

**Phase C — High-traffic screens.** [share/shares.html](templates/share/shares.html) (validates DataTable). [share/logs.html](templates/share/logs.html) (validates DataTable a second time). [list.html](templates/list.html) (the heavy one — FileTable, Uploader, MetadataEditor, FilePreview, 7 modals, PathPicker).

**Phase D — Permissions and groups.** [share/permissions.html](templates/share/permissions.html). [groups/*.html](templates/groups/). [ssh/*.html](templates/ssh/).

**Phase E — Edges.** Dialog includes folded into their consuming pages. [share/links.html](templates/share/links.html), [search/search_files.html](templates/search/search_files.html), [viz/cloud.html](templates/viz/cloud.html). Registration / error pages — pure crispy verification, no Vue.

**Phase F — Cleanup.** Delete retired files (below). Run axe sweep on every screen. Manual a11y audit. Delete `legacy-icon-shim.css`. Open PR.

## Verification

**Per-page workflow during development (Playwright-driven):**

For every page touched in §"Per-screen migration":
1. Navigate to the page in Playwright at `http://bioshare:9999/...`
2. Take a baseline screenshot for visual sanity
3. Run axe-core in-page (the DEBUG-mode `<script>` injection below already loads it on the page; if not, evaluate `axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa']}})` directly via the page's JS console)
4. Exercise the page's primary actions (click row checkbox, open modal, submit form) and confirm each works without console errors
5. Tab through every interactive element; confirm focus is visible, focus order is logical, modals trap focus, Esc closes everything that should close
6. For pages with JSON API interaction (file ops, permissions, share creation): watch network panel during the action; confirm request body and response shape match the API contract in §"JSON endpoint shapes consumed"
7. Resize to 320px width; confirm no horizontal scroll except within data tables, sidebar collapses, permission matrix becomes accordion
8. Fix any axe violations or interaction bugs before moving to the next page

**Automated (axe-core, in-page, DEBUG only):**

```django
{% if debug %}
<script src="{% static 'lib/axe-core/axe.min.js' %}"></script>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa'] }})
       .then(r => r.violations.length
         ? console.warn('axe', r.violations)
         : console.log('axe: 0 violations'));
  });
</script>
{% endif %}
```

Re-run axe after dynamic mutations: `Modal.onMounted` calls `axe.run(modalEl, …)`.

**Human-required passes (still needed even with Playwright):**
- Screen reader: NVDA + Firefox (Windows) and VoiceOver + Safari (macOS) — read every page, open every modal, trigger every toast. Playwright cannot substitute for real AT.
- Subjective visual judgment: is the focus ring obvious against the surrounding color? Does the "modified" state read clearly?
- Cross-browser: Playwright defaults to Chromium; do a spot-check in Firefox and Safari on the heaviest screens (list.html, permissions.html).
- 200% browser zoom (Playwright handles 320px viewport, but actual zoom semantics differ slightly — verify in a real browser).

## Key risks and how each is handled

1. **django-compressor + ES modules.** Module scripts inside `{% compress js %}` get concatenated as plain text and break. **Fix:** put the `window.BIOSHARE = {…}` bootstrap and the importmap inside `{% compress js %}` (the importmap is a `<script type="importmap">` block, not a `<script src>`, so it survives concatenation); load `static/js/app/main.js` and the per-page `pages/*.js` as bare `<script type="module">` outside the compress block.

   **Required importmap shape** (emitted from `base.html`):
   ```html
   <script type="importmap">
   { "imports": {
       "vue": "{% static 'lib/vue/vue.esm-browser.prod.js' %}",
       "reka-ui": "{% static 'lib/reka-ui/reka-ui.bundle.esm.js' %}"
   } }
   </script>
   ```
   Both library `vue` and `reka-ui` are bare specifiers used by Reka UI's bundle internally (`vue`) and by our component files (both). All transitive deps of Reka UI are inlined into the bundle, so no other importmap entries are needed.

2. **File upload progress.** `fetch` has no progress events. **Fix:** use `XMLHttpRequest` with `xhr.upload.onprogress`; upload one file at a time (current behavior). `role="progressbar"`. Drag-drop stretched goal via root `@dragover/@drop`.

3. **DataTable feature parity with ng-table.** Server-side pagination, column filtering, sorting, URL persistence. **Fix:** generic `<DataTable :endpoint :columns :page-size :url-state="…">`. Internal `fetch(endpoint + '?' + params)` against DRF, expects `{count, results}`. URL persistence in [url-state.js](static_files/js/app/url-state.js) mirrors existing `?tableSettings.page=…&tableSettings.sorting.updated=desc&cols.Share=true` format so existing bookmarks keep working.

4. **`BC.ajax` global.** Many call sites during migration. **Fix:** `api.js` keeps `window.BC = { ajax, handle_ajax_errors, ... }` aliases until the last caller is gone, then delete.

5. **`csrf.js` + global ajaxSetup.** **Fix:** `api.js` injects `X-CSRFToken` header per request from `window.BIOSHARE.csrfToken` (template-rendered).

6. **`{% verbatim %}` collisions.** Vue uses `{{ }}` like Angular did. **Fix:** Vue templates live in backtick strings inside `.vue.js` files, not in Django templates — so `{% verbatim %}` blocks naturally disappear.

7. **Bootstrap 2 → 5 class drift.** `span3/span9/pull-left/pull-right/well/nav-list/nav-header/input-block-level/btn-link/progress-striped progress-success`. **Fix:** mechanical find-and-replace pass in Phase F: `span3` → `col-md-3`, `pull-left` → `float-start`, `well` → `card card-body bg-light`, `input-block-level` → `w-100`, etc.

8. **Sidebar `{% cache %}` and Vue.** **Fix:** keep `{% cache 60 sidebar request.user.username %}`; emit data via `{{ user_shares|json_script:"sidebar-data" }}`; `<SidebarShares>` reads from that. Cache benefit preserved.

9. **`{% trans %}` in Vue components.** **Fix:** components contain zero user-visible English. All strings flow in via props/slots from the Django template, e.g. `<ConfirmDialog :title="'{% trans "Confirm delete" %}'" :confirm-label="'{% trans "Delete" %}'">`.

10. **Compressor cache.** Stale bundles in `static/CACHE/`. **Fix:** PR notes include `python manage.py compress --force` (or delete the dir).

11. **ES module identity across imports.** Browsers cache modules by URL. Adding `?v=N` cache-busting to a *top-level* import without propagating it to nested imports loads two instances of the module — two separate `reactive()` proxies — and mutations in one don't trigger watchers in the other. **Symptom hit during Phase A:** `state.confirm = {...}` from page code didn't fire reactivity in `<ConfirmDialog>` because the page imported `state.js?v=N` (fresh) while the component imported `state.js` (cached). **Fix:** never cache-bust selectively. Either bust nothing (force-reload by navigating away and back) or use one consistent versioned import map for all modules. Module URL identity is reactivity identity.

12. **Reka UI auto-close buttons fire before user @click.** `AlertDialogAction` / `AlertDialogCancel` (and `DialogClose`) close the dialog via Reka's internal click handler that runs *before* user-supplied `@click`. **Symptom:** `@click="resolve(true)"` sees state.confirm already nulled by the onOpenChange path → resolves to false. **Fix in [ConfirmDialog.vue.js](static_files/js/app/components/ConfirmDialog.vue.js):** use `@click.capture` to set a `pendingResult` flag *before* Reka's close runs, and `onOpenChange` reads the flag to decide the resolution value. Apply the same pattern when wiring close-buttons inside `<Modal>`.

13. **Reka UI dropdown is modal by default.** `DropdownMenuRoot` defaults to `modal=true`, which applies `aria-hidden` to the rest of the page while the menu is open — axe flags this as `aria-hidden-focus` for the skip-link. **Fix in [DropdownMenu.vue.js](static_files/js/app/components/DropdownMenu.vue.js):** pass `:modal="false"` on `DropdownMenuRoot`. The dropdown is a transient menu, not a modal; background should stay interactive.

## Files retired (delete in Phase F)

**Vendored libs (delete entire directories):** [lib/angular/](static_files/lib/angular/), `lib/angular-checklist/`, `lib/ng-table/`, `lib/ui-bootstrap/`, `lib/bootstrap/` (BS2), `lib/datatables/`, `lib/dynatree/`, `lib/jquery_upload/`, `lib/textcomplete/`, `lib/jquery-1.10.1.min.js`, `lib/jquery.bootstrap-growl.min.js`, `lib/handlebars.js`, `lib/json2.min.js`, `lib/famfamfam-bootstrap/` (after icon shim removed).

**First-party JS:** [bioshare.js](static_files/js/bioshare.js), [csrf.js](static_files/js/csrf.js), [django_js_utils.js](static_files/js/django_js_utils.js), [jsurls.js](static_files/js/jsurls.js), [lib.js](static_files/js/lib.js), [resources/](static_files/js/resources/), [services/](static_files/js/services/), [controllers/](static_files/js/controllers/), [directives/](static_files/js/directives/), [share/main.js](static_files/js/share/main.js), [share/permissions.js](static_files/js/share/permissions.js), [share/search.js](static_files/js/share/search.js), [ssh/ssh_keys.js](static_files/js/ssh/ssh_keys.js).

**Templates:** [templates/handlebars/](templates/handlebars/) (entire dir).

**Kept untouched:** [lib/d3/](static_files/lib/d3/) (cloud.html viz), [static_files/images/](static_files/images/), [templates/wget_listing.html](templates/wget_listing.html).

## Critical files for execution

- [templates/base.html](templates/base.html) — shell rewrite that gates every child page
- [templates/list.html](templates/list.html) — heaviest single screen (file browser + 7 modals + uploads)
- [static_files/js/app/main.js](static_files/js/app/main.js) (new) — Vue bootstrap, singleton mounts
- [static_files/js/app/components/DataTable.vue.js](static_files/js/app/components/DataTable.vue.js) (new) — ng-table feature parity gates shares/logs/groups screens
- [static_files/js/app/api.js](static_files/js/app/api.js) (new) — fetch wrapper + CSRF + 401/429 routing; replaces every `BC.ajax` and [csrf.js](static_files/js/csrf.js)
- [requirements.txt](requirements.txt), [settings/settings.py](settings/settings.py) — the only backend touches

## How to verify end-to-end before merging

1. Run `python manage.py compress --force && python manage.py collectstatic --noinput`. Start `docker-compose up`.
2. **Playwright sweep:** I walk through every page in §"Per-screen migration" via Playwright at `http://bioshare:9999`. Each must render, perform its primary action without console errors, and emit zero axe violations against WCAG 2.1 AA. Screenshots captured per page for diff-against-baseline review.
3. **JSON shape verification:** during the Playwright sweep, network panel confirms request/response bodies for every API call match the contracts in §"JSON endpoint shapes consumed" (no accidental drift).
4. **URL state verification:** Playwright navigates to a shares-list URL with `?tableSettings.page=2&tableSettings.sorting.updated=desc` — DataTable should restore the same state ng-table did. Confirms bookmark compatibility.
5. **Human passes** (the ones Playwright can't do): NVDA + Firefox on Windows and VoiceOver + Safari on Mac, on the four heavy screens — [base.html](templates/base.html) chrome, [shares.html](templates/share/shares.html), [list.html](templates/list.html), [permissions.html](templates/share/permissions.html). Plus a 200% browser-zoom pass and a Firefox + Safari Chromium-parity spot-check.
6. Open the PR back to `django5-upgrade` (or directly to `master`, depending on whether the Django 5 work is ready to land on its own). If anything goes sideways, revert is `git checkout django5-upgrade` — backend is untouched apart from the crispy swap, which is independently reversible.
