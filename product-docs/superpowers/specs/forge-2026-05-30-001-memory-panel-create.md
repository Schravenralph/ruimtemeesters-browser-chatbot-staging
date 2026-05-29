# Forge Spec: "+ New memory" button + dialog on the memory panel

**Cycle:** 3 | **Size:** medium

## What

A "+ New memory" button on `/memory` that opens a modal dialog with
fields for `name`, `description`, `type`, `scope`, and `content`.
Submits via the existing `saveMemoryEntry` API. On success, the panel
list refreshes and the new entry is visible (and editable, post the
shim double-prefix fix).

## Why

The panel can already **edit** and **forget** existing entries, but
there's no UI path to **create** one. Advisors who want to preload
preferences ("BOPA-conclusies kort en zakelijk") or feedback patterns
have to go through chat, which scatters the workflow and gives them no
preview before save.

The shim double-prefix fix in MCP-Servers #124 means newly-created
entries now stamp with the actual `clerk:<sub>` — so a Create button
adds genuinely-mutable rows, not orphaned-from-day-one entries.

## Success criteria

1. A "+ New memory" button visible on the panel header.
2. Clicking opens a modal with the five fields. Required: name,
   description, type, content. Optional: scope (defaults to `user`),
   project_id (only shown + required when scope=`project`).
3. Client-side validation catches obvious gaps (empty name, name >120
   chars, description >200, content >65 536) before submit.
4. Submit calls `saveMemoryEntry`. On 2xx, the list refreshes and the
   new entry appears.
5. On error (network / 4xx), surface the BFF detail in the dialog
   (don't dismiss).
6. Cancel button closes without saving.

## Approach

- New component `src/lib/components/memory/MemoryCreateModal.svelte`.
  Self-contained: own state, accepts only `show` + `onCreated` props.
- Reuse the existing Modal common component (other panels do —
  `ShareChatModal.svelte` is the closest pattern).
- The panel's `+page.svelte` adds a button next to the search input
  and renders the modal at the end. The `onCreated` callback calls
  the existing `refresh()` to repopulate the list.
- Mirror `SaveMemoryRequest`'s Pydantic invariant client-side: scope
  ↔ project_id (project requires id; non-project forbids id).

## Not doing

- Bulk import / JSON paste — out of scope; single entries only.
- Markdown preview of `content` — content is plain text in the
  backend; no preview needed for v1.
- Template chooser ("save a preference / save a feedback / …") —
  the `type` select already covers this; templates are a separate
  later cycle.
- Editing the `name`/`type`/`scope` of an existing entry — those are
  upsert-key fields; mutating them would create a phantom row. Stays
  as today: only `description` + `content` are editable on existing
  rows.
