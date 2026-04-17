# WCAG 2.1 AA Accessibility Remediation Plan

**Deadline:** April 24, 2026
**Standard:** WCAG 2.1 AA
**Reference:** https://digitalaccessibility.ucop.edu/frequently-asked-questions/

Stages are ordered from safest (pure additive HTML attributes, zero behavioral risk) to most complex (JS refactors with regression risk). Within each stage, higher-impact WCAG criteria are listed first.

---

## Stage 1 — Pure HTML Attribute Additions (Zero Risk)

These changes add missing attributes without altering structure, styling, or behavior. Nothing can break.

### 1a. `lang` attribute on standalone `<html>` elements (WCAG 3.1.1 Language of Page)
- [x] `templates/429.html` line 1 — added `lang="en"` to `<html>`
- [x] `templates/403.html`, `templates/404.html`, `templates/500.html` — all extend `base.html` which already has `lang="en"`
- [x] `templates/registration/base.html` line 4 — already has `lang="en"`

### 1b. Alt text on images (WCAG 1.1.1 Non-text Content)
- [x] `templates/footer.template.html` line 4 — added `alt="UC Davis Genomics Core wordmark"`
- [x] `templates/500.html` line 6 — changed empty `alt=""` to `alt="Server error"`

### 1c. `scope` attributes on table headers (WCAG 1.3.1 Info and Relationships)
- [x] `templates/list.html` line 156 — added `scope="col"` to all nine headers plus `<span class="sr-only">` text for visually empty columns (Select, Type, Actions)
- [x] `templates/wget_listing.html` line 3 — added `scope="col"`
- [x] `templates/groups/manage_group.html` lines 17-19 — added `scope="row"` to row headers

Note: `templates/search/search_files.html` lines 15-16, `templates/share/links.html` line 36, `templates/ssh/list_keys.html` line 11, and `templates/share/permissions.html` line 57 already have correct `scope` attributes.

### 1d. Associate form labels with inputs (WCAG 1.3.1 Info and Relationships)
- [x] `templates/dialogs/email_users.html` line 10 — added `aria-label="Select all recipients"` to the "All" checkbox
- [x] `templates/dialogs/email_users.html` line 11-12 — added `for="email-subject"` / `id="email-subject"` pairing
- [x] `templates/dialogs/email_users.html` line 13-14 — added `for="email-body"` / `id="email-body"` pairing
- [x] `templates/dialogs/share_read_only.html` line 11 — changed to explicit `for="share-email"` / `id="share-email"` pairing
- [x] `templates/groups/manage_group.html` line 42 — added `<label for="add-group-user" class="sr-only">Add user by email</label>` and `id="add-group-user"`
- [x] `templates/list.html` line 267 — added `<label for="searchBox" class="sr-only">Search files in share</label>`

### 1e. `aria-label` on icon-only interactive elements (WCAG 1.1.1, 4.1.2 Name, Role, Value)

- [x] `templates/list.html` — directory row: added `aria-label` to `fam-tag-blue` ("Edit metadata"), `fam-pencil` ("Rename"), `fam-group-add` link ("Make this folder its own share" on `<a>`, `aria-hidden` on `<i>`), unlink `fam-delete` link (`aria-label` on `<a>`, `aria-hidden` on `<i>`)
- [x] `templates/list.html` — file row: added `aria-label` to `fam-tag-blue` ("Edit metadata"), `fam-eye` ("Preview file contents"), `fam-pencil` ("Rename")
- [x] `templates/list.html` — shared subfolder icon: added `aria-label="View shared subfolder '{{dir.share.name}}'"` to `<a>`, `aria-hidden="true"` to `<i>`
- [x] `templates/list.html` line 69 — `fam-help` icon: added `aria-label` matching the title text
- [x] `templates/handlebars/list_files.html` — directory, link, and file templates: added `aria-label` to all action icons; added `aria-label` and `aria-hidden` to unlink `<a>`/`<i>` pair
- [x] `templates/ssh/list_keys.html` line 14 — added `aria-label="Delete SSH key {{key.name}}"`
- [x] `templates/groups/manage_group.html` line 46 — added `aria-label="Remove user"` to trash icon

### 1f. `aria-label` on unlabeled checkboxes (WCAG 1.3.1, 4.1.2)
- [x] `templates/list.html` line 156 — added `aria-label="Select all files"` to toggle checkbox
- [x] `templates/list.html` line 164 — added `aria-label="Select {{ dir.name }}"` to directory row checkbox
- [x] `templates/list.html` line 202 — added `aria-label="Select {{ file.name }}"` to file row checkbox
- [x] `templates/handlebars/list_files.html` lines 19, 33, 47 — added `aria-label="Select {{name}}"` to all three template checkboxes

**WCAG criteria covered:** 1.1.1 Non-text Content, 1.3.1 Info and Relationships, 3.1.1 Language of Page, 4.1.2 Name/Role/Value

---

## Stage 2 — CSS Overrides (Low Risk, High Impact)

These are append-only CSS additions to `bioshare.css`. No vendor files are modified.

### 2a. Restore focus indicators (WCAG 2.4.7 Focus Visible) — CRITICAL
- [x] Appended `*:focus-visible` override to `static_files/css/bioshare.css` — restores keyboard focus outlines suppressed by Bootstrap, DataTables, and other vendor CSS without affecting mouse users

### 2b. Color-only error indicator (WCAG 1.4.1 Use of Color)
- [x] `static_files/css/bioshare.css` — added `font-weight: bold` to `.error` class
- [x] `templates/share/permissions.html` — added `border-left: 4px solid #cc8800` to `.modified` rows

### 2c. Skip navigation link styling (WCAG 2.4.1 Bypass Blocks)
- [x] Appended `.skip-link` styles to `static_files/css/bioshare.css` — offscreen by default, visible on focus

**WCAG criteria covered:** 2.4.7 Focus Visible, 1.4.1 Use of Color, 2.4.1 Bypass Blocks

---

## Stage 3 — Modal Dialog Accessibility (Additive Attributes, Moderate Scope)

All 12 Bootstrap modals lack `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`. These are attribute additions on existing elements — no structural change, but there are many modals to update.

### Pattern
```html
<!-- Add to each modal's outer div -->
role="dialog" aria-modal="true" aria-labelledby="[modal]-title"

<!-- Add id to each modal's heading -->
<h3 id="[modal]-title">...</h3>
```

### Modals in `templates/list.html`
- [x] Line 280 — `id="new-folder"`: added `role="dialog" aria-modal="true" aria-labelledby="new-folder-title"`, added `id` to `<h3>`
- [x] Line 297 — `id="new-link"`: added `role="dialog" aria-modal="true" aria-labelledby="new-link-title"`, added `id` to `<h3>`
- [x] Line 314 — `id="modify-name"`: added `role="dialog" aria-modal="true" aria-labelledby="modify-name-title"`, added `id` to `<h3>`
- [x] Line 332 — `id="rsync-download"`: added `role="dialog" aria-modal="true" aria-labelledby="rsync-download-title"`, added `id` to `<h3>`
- [x] Line 349 — `id="wget-download"`: added `role="dialog" aria-modal="true" aria-labelledby="wget-download-title"`, added `id` to `<h3>`
- [x] Line 366 — `id="sftp-dialog"`: added `role="dialog" aria-modal="true" aria-labelledby="sftp-dialog-title"`, added `id` to `<h3>`
- [x] Line 400 — `id="rsync-upload"`: added `role="dialog" aria-modal="true" aria-labelledby="rsync-upload-title"`, added `id` to `<h3>`
- [x] Line 418 — `id="move-to-modal"`: added `role="dialog" aria-modal="true" aria-labelledby="move-to-modal-title"`, added `id` to `<h3>`
- [x] Line 433 — `id="edit-metadata"`: added `role="dialog" aria-modal="true" aria-labelledby="edit-metadata-title"`, added `id` to `<h3>`

### Modals in dialog includes
- [x] `templates/dialogs/email_users.html` — added `role="dialog" aria-modal="true" aria-labelledby="email-users-title"`, added `id` to `<h3>`
- [x] `templates/dialogs/preview_file.html` — added `role="dialog" aria-modal="true" aria-labelledby="preview-file-title"`, added `id` to `<h3>`
- [x] `templates/dialogs/share_read_only.html` — added `role="dialog" aria-modal="true" aria-labelledby="share-read-only-title"`, added `id` to `<h3>`

### AngularJS modal template
- [x] `templates/groups/manage_group.html` — verified ui-bootstrap's `$uibModal` automatically adds `role="dialog"` and `aria-labelledby` to its modal wrapper. No manual change needed

All existing close buttons already have `aria-label="Close"` — verified across all modals.

**WCAG criteria covered:** 1.3.1 Info and Relationships, 4.1.2 Name/Role/Value

---

## Stage 4 — Heading Hierarchy and Semantic Structure (Low–Medium Risk)

Changes to heading levels may affect styling. Use `class="h3"` etc. to preserve visual appearance while correcting the document outline.

### 4a. Page-level heading issues (WCAG 1.3.1)
- [x] `templates/search/search_files.html` line 11 — changed `<h3>` to `<h1 class="h3">` to be the page heading while preserving size
- [x] `templates/list.html` line 36 — changed `<h4>` breadcrumb to `<h2 class="h4">` for correct h1→h2 hierarchy
- [x] `templates/share/shares.html` — verified heading tree is correct (h2→h3→h4), no change needed

### 4b. Modal heading levels
- [x] All modals use `<h3>` inside modals with `aria-labelledby` — acceptable per WCAG. No change needed.

### 4c. Subheadings within modals
- [x] `templates/list.html` rsync-download modal — changed "Download all" and "Download selected" from `<h3>` to `<h4>`
- [x] `templates/list.html` wget-download modal — changed "Linux/Mac" and "Windows" from `<h3>` to `<h4>`
- [x] `templates/list.html` sftp-dialog modal — changed symlink warning, "Connecting" headings (both auth and anon) from `<h3>` to `<h4>`

**WCAG criteria covered:** 1.3.1 Info and Relationships

---

## Stage 5 — Semantic Element Upgrades (Medium Risk — Requires Smoke Testing)

Convert non-semantic interactive elements to proper `<button>` elements for keyboard accessibility. These changes may affect CSS selectors or JS event delegation, so each file should be tested after modification.

### 5a. Anchors used as buttons without `href` (WCAG 2.1.1 Keyboard, 4.1.2)

Anchors without `href` are not focusable by keyboard in all browsers:

- [x] `templates/list.html` line 66 — `<a class="pointer" ng-if="!size" ng-click="calculate(...)">Calculate...</a>` → `<button class="btn btn-link" ng-if="!size" ng-click="calculate(...)">Calculate...</button>`
- [x] `templates/share/shares.html` lines 49-50 — `<a class="pointer" ng-click="toggleFilters()">Show/Hide</a>` → `<button class="btn btn-link" ng-click="toggleFilters()">Show/Hide</button>`
- [x] `templates/share/shares.html` line 74 — `<a class="pointer" ng-click="setFilter('tags',tag.name)">` → `<button class="btn btn-link" ng-click="setFilter('tags',tag.name)">`
- [x] `templates/share/shares.html` lines 75-77 — similar `<a class="pointer" ng-click="setFilter(...)">` for Owner, Users, Groups columns → `<button class="btn btn-link">` (added `td .btn-link { padding:0; margin:0 }` to bioshare.css to prevent extra spacing)

### 5b. `<i>` elements used as buttons (WCAG 2.1.1, 4.1.2)

Icon elements with `data-action` click handlers should be `<button>` wrappers:

- [x] `templates/groups/manage_group.html` line 46 — `<i class="icon-trash" ng-click="removeUser(user)">` → `<button class="btn btn-link btn-sm" ng-click="removeUser(user)" aria-label="Remove user"><i class="icon-trash" aria-hidden="true"></i></button>`

For the `data-action` icons in `templates/list.html` and `templates/handlebars/list_files.html`, wrapping each in `<button>` is ideal but may disrupt DataTables column sizing. A lower-risk alternative for Stage 5 is to add `role="button" tabindex="0"` to each `<i>` with `data-action` and add keyboard handling in Stage 6. Full button conversion can be a follow-up.

### 5c. `<a href="#">` action links (WCAG 2.1.1)

These are focusable (they have `href`) but navigate to `#` on activation, which is a minor UX issue:

- [x] `templates/list.html` line 293 — `<a href="#" class="btn btn-primary" id="create-folder">Create</a>` → `<button class="btn btn-primary" id="create-folder">Create</button>` (JS already binds click to `#create-folder`)
- [x] `templates/list.html` line 310 — same for `id="create-link"`
- [x] `templates/list.html` line 327 — same for `id="rename-button"`
- [x] `templates/list.html` line 219 — `<a href="#" data-action="calculate-md5">Calculate</a>` → `<button class="btn btn-link" data-action="calculate-md5">Calculate</button>` (and in handlebars template line 53)

**WCAG criteria covered:** 2.1.1 Keyboard, 4.1.2 Name/Role/Value

---

## Stage 6 — JavaScript: Keyboard Support and Dynamic Announcements (Medium–High Risk)

These changes modify JS behavior. Each should be tested with keyboard navigation and a screen reader.

### 6a. Add keyboard handlers to click-only `data-action` elements (WCAG 2.1.1)

`static_files/js/share/main.js` lines 427-431 register click-only handlers:
```javascript
$(document).on('click','[data-action="edit-metadata"]',open_metadata_form);
$(document).on('click','[data-action="preview"]',preview_share_action);
$(document).on('click','[data-action="calculate-md5"]',calculate_md5);
$(document).on('click','[data-action="modify-name"]',open_rename_form);
$(document).on('click','[data-action="unlink"]',unlink);
```

- [x] Changed each to `'click keydown'` with `a11y_handler()` guard wrapper
- [x] `static_files/js/share/main.js` — `$('#file-table').on('click','span.tag',...)` → added keydown handler for tag filtering
- [x] `static_files/js/ssh/ssh_keys.js` — `$('[data-action="delete-key"]').click(...)` → added keydown
- [x] `static_files/js/share/permissions.js` — `.check_all` and `.uncheck_all` click handlers on `<i>` icons → added keydown

### 6b. Dynamically created icons need `role`, `tabindex`, `aria-label` (WCAG 4.1.2)

`static_files/js/share/permissions.js` creates icons dynamically without accessibility attributes:

- [x] Line 68 — `.append('<i class="fam-email"...')` → added `aria-hidden="true"`
- [x] Line 73 — `.append('<i class="fam-cross"...')` → added `role="button" tabindex="0" aria-label="Remove access from this user"`
- [x] Line 129 — `<i class="fam-accept check_all">` and `<i class="fam-delete uncheck_all">` → added `role="button" tabindex="0" aria-label`
- [x] Line 133 — `<i class="fam-error-add" ...>` → added `aria-hidden="true"`
- [x] Line 134 — dynamically created permission checkboxes → added `label_permission_checkboxes()` helper that sets `aria-label` combining permission name and username/group

### 6c. `aria-live` regions for dynamic content (WCAG 4.1.3 Status Messages)

- [x] `templates/list.html` — `<div id="messages">` → added `aria-live="polite" aria-atomic="true"`
- [x] `templates/list.html` — `<div id="searchResults">` → added `aria-live="polite"`
- [x] `templates/dialogs/preview_file.html` and `templates/dialogs/email_users.html` — `<span id="lines-loaded">` → added `aria-live="polite"`
- [x] `templates/share/permissions.html` — `<div id="messages">` → added `aria-live="polite"`

Note: Do NOT add `aria-live` to high-frequency update targets like `#preview-file-area` (would be excessively noisy). The `#lines-loaded` summary is the right element to announce.

### 6d. Modal focus management (WCAG 2.4.3 Focus Order)

Bootstrap 2.x `modal('show')` may not automatically move focus into the modal or return focus on close.

- [x] Added global `.modal` `shown` handler in main.js — focuses first visible input/button/textarea/link inside modal, stores trigger element
- [x] Added global `.modal` `hidden` handler — returns focus to the element that opened the modal
- [x] `$uibModal.open()` calls in `group-controller.js` and `message-directives.js` — ui-bootstrap handles focus management automatically, no change needed

Recommended approach: add a global handler:
```javascript
$('.modal').on('shown', function() {
    $(this).find('input, button, textarea, a[href]').filter(':visible').first().focus();
});
```

**WCAG criteria covered:** 2.1.1 Keyboard, 4.1.2 Name/Role/Value, 4.1.3 Status Messages, 2.4.3 Focus Order

---

## Stage 7 — Third-Party Widget and Framework Accessibility (Highest Complexity)

These require the deepest investigation and may involve vendor library configuration, patches, or replacement.

### 7a. DataTables accessibility
- [x] Verified DataTables 1.9.4 already includes `aria-sort` and `aria-label` on sortable column headers, and wraps its filter input in an implicit `<label>Filter: <input></label>`. No changes needed.
- [x] Sort headers announce sort state via `aria-sort` and `aria-label` attributes built into the library
- [x] Table structure is preserved by DataTables — original `<table>`, `<thead>`, `<th scope="col">` remain intact

### 7b. Dynatree (file move tree widget)
- [x] Dynatree has zero native ARIA support. Added post-render ARIA via callbacks:
  - `onCreate`: sets `role="treeitem"`, `aria-label`, and `aria-expanded` on each `<li>` node
  - `onPostInit`: sets `role="tree"` on the root `<ul>` and `role="group"` on nested `<ul>` elements
  - `onExpand`: updates `aria-expanded` when nodes are expanded/collapsed
- [x] Dynatree's built-in keyboard navigation (arrow keys, +/- for expand/collapse) works without modification

### 7c. AngularJS ng-table
- [x] Added Angular directive in `ng-table-services.js` that patches ng-table post-render:
  - Adds `aria-label="Filter by [column]"` to all filter `<input>` elements
  - Adds `aria-sort` (`ascending`/`descending`/`none`) to sortable `<th>` headers
  - Re-patches on data reload via `$watch` and `ngTableAfterReloadData` event
- [x] Covers both `shares.html` and `manage_group.html` ng-table instances

### 7d. Bootstrap typeahead / textcomplete autocomplete
- [x] `bioshare.js` — Patched typeahead instance: added `role="combobox"`, `aria-autocomplete="list"`, `aria-haspopup="listbox"`, `aria-expanded` to input; `role="listbox"` on menu; `role="option"` on items. Show/hide wrappers toggle `aria-expanded`.
- [x] `permissions.js` — Added `role="combobox"`, `aria-autocomplete`, `aria-expanded`, `aria-haspopup` to `#addUser`. Hooked `textComplete:show`/`textComplete:hide` events to set `role="listbox"`/`role="option"` on dropdown and toggle `aria-expanded`.

### 7e. bootstrapGrowl toast notifications
- [x] Monkey-patched `$.bootstrapGrowl` in `bioshare.js` to add `role="alert"` to each toast div. This ensures all growl notifications (success, error, info) are announced by screen readers.

### 7f. jQuery file upload
- [x] Added `aria-label="Upload files via browser"` to `<input id="fileupload" type="file">` in `list.html`. The input is keyboard-operable (real `<input type="file">` with `opacity:0` overlay pattern).

**WCAG criteria covered:** 4.1.2 Name/Role/Value, 2.1.1 Keyboard, 4.1.3 Status Messages, 1.3.1 Info and Relationships

---

## Stage 8 — Audit Follow-up Fixes (Mixed Risk)

Fixes identified by code-level accessibility audit after Stages 1-7 were implemented.

### 8a. Fix mismatched `<button>`/`</a>` tags (CRITICAL — DOM corruption)
- [x] `templates/list.html` lines 30-31 — `<button>...</a>` → `<button>...</button>` for Email and Share buttons

### 8b. Add `tabindex="0"` and `role="button"` to `data-action` `<i>` icons (WCAG 2.1.1, 4.1.2)

Completes the deferred work from Stage 5b. Icons had `aria-label` (Stage 1e) and keyboard handlers (Stage 6a) but were not focusable.

- [x] `templates/list.html` line 186 — directory row `edit-metadata` and `modify-name` icons
- [x] `templates/list.html` lines 222-224 — file row `edit-metadata`, `preview`, `modify-name` icons
- [x] `templates/handlebars/list_files.html` lines 27, 41, 55 — all three template icon sets
- [x] `templates/ssh/list_keys.html` line 14 — `delete-key` icon

### 8c. Convert remaining `<a>` without `href` to `<button>` (WCAG 2.1.1)
- [x] `templates/list.html` line 136 — `<a id="open-move-modal">` → `<button>`
- [x] `templates/list.html` line 138 — `<a id="delete-button">` → `<button>`

### 8d. Add ARIA combobox pattern to search textcompletes (WCAG 4.1.2)
- [x] `static_files/js/share/search.js` — added `role="combobox"`, `aria-autocomplete`, `aria-expanded`, `aria-haspopup` to `#search_users` and `#search_tags`; hooked `textComplete:show`/`textComplete:hide` for `aria-expanded` and `role="listbox"`/`role="option"`
- [x] Removed stray bare `search_tags` reference (dead code on line 72)

### 8e. Fix `.error` color contrast (WCAG 1.4.3)
- [x] `static_files/css/bioshare.css` — changed `color: red` (#FF0000, 3.99:1) to `color: #b30000` (5.5:1 contrast ratio)

### 8f. Add `aria-hidden="true"` to decorative icons (WCAG 1.1.1)
- [x] `templates/list.html` lines 207, 209 — `fam-link` and `fam-page-white` file icons
- [x] `templates/share/shares.html` line 71 — `icon-lock` inside locked share link
- [x] `templates/handlebars/list_files.html` lines 21, 35, 49 — `fam-folder`, `fam-folder-link`, `fam-page-white`

### 8g. Improve `429.html` structure (WCAG 4.1.1)
- [x] `templates/429.html` — added `<!DOCTYPE html>`, `<head>`, `<meta charset>`, `<title>`

**WCAG criteria covered:** 4.1.1 Parsing, 1.1.1 Non-text Content, 1.4.3 Contrast, 2.1.1 Keyboard, 4.1.2 Name/Role/Value

---

## Summary

| Stage | Description | Risk | Key WCAG Criteria | Estimated Scope |
|-------|-------------|------|-------------------|-----------------|
| 1 | HTML attribute additions | None | 1.1.1, 1.3.1, 3.1.1, 4.1.2 | ~30 element changes across 8 files |
| 2 | CSS focus + color fixes | Low | 2.4.7, 1.4.1, 2.4.1 | 1 file (bioshare.css), append only |
| 3 | Modal ARIA attributes | Low | 1.3.1, 4.1.2 | 12 modals across 4 files |
| 4 | Heading hierarchy | Low-Med | 1.3.1 | ~8 heading changes across 3 files |
| 5 | Semantic element upgrades | Medium | 2.1.1, 4.1.2 | ~15 element changes, 4 files + Handlebars |
| 6 | JS keyboard + aria-live | Medium | 2.1.1, 4.1.2, 4.1.3 | 4 JS files + 4 templates |
| 7 | Third-party widget audit | High | 4.1.2, 2.1.1, 1.3.1 | Investigation + potential patches/replacements |
| 8 | Audit follow-up fixes | Mixed | 4.1.1, 1.1.1, 1.4.3, 2.1.1, 4.1.2 | Bug fixes + deferred items across 7 files |

**Stages 1-3** are safe, mechanical changes that address the majority of WCAG violations and should be completed first. **Stage 2a (focus indicators)** is the single highest-impact change — without visible focus, the entire application is effectively unusable by keyboard.

**Stages 4-5** have moderate risk and moderate impact. **Stage 6** is where the real keyboard accessibility for dynamic interactions gets fixed. **Stage 7** is the hardest to scope and may require vendor library decisions.
