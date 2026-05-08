# Forge Spec: rm-memory user-facing panel (`/memory/user`)

**Cycle:** 6 | **Clock:** new session, ~0h elapsed | **Size:** medium-large

## What

Closes the user-visible side of #47. Adds a Svelte route `/memory/user` and a reusable `MemoryPanel.svelte` that consumes the BFF endpoints shipped in #60 + #61 (`/api/v1/rm-memory` list / get / save / forget). Users can now see what the assistant has remembered about them and edit or delete entries themselves — no more "ask the chatbot to forget that".

```
src/routes/(app)/memory/user/+page.svelte
src/lib/components/memory/MemoryPanel.svelte         # shared, scope-agnostic
src/lib/components/memory/MemoryEntryRow.svelte      # one row, with edit/delete
src/lib/components/memory/EditMemoryModal.svelte     # forget-then-save flow
src/lib/apis/rm-memory.ts                            # typed client (list/get/save/forget)
src/lib/i18n/locales/en-US/translation.json          # new keys + npm run i18n:parse
```

Sidebar gets a "Memory" entry pointing at `/memory/user`. The project route (`/memory/project/[id]`) is **deferred** — there's no project-binding UX in this chatbot today, so a project route would be unreachable. Documented as a follow-up; the shared `MemoryPanel` already takes a `scope` prop so adding the project route later is one new `+page.svelte`.

## Why

Today users can't see what the system has saved about them. They have to ask the assistant "what do you remember?" and trust the answer; they can't fix a wrong entry without asking the assistant to call `forget_memory` on their behalf. That's both a privacy gap and a bad UX.

The OSS evaluation (mem0 / Letta / Zep / OpenWebUI native / Cognee / LangMem) settled on building minimal scaffolding ourselves — recorded in `project_memory_panel_oss_eval.md`. Cycles 4 + 5 shipped the BFF; this cycle is the UI that closes the loop.

## Success criteria

1. Visiting `/memory/user` while signed in renders the panel; visiting unauth → redirects to login (the `(app)` layout already enforces this).
2. The panel calls `GET /api/v1/rm-memory` on mount and lists entries grouped by `type` (user, feedback, project, reference, session-summary). Each row shows: name, description, scope badge, `updated_at` formatted with `toLocaleString`, edit + delete actions.
3. Empty state copy is verbatim from #47: *"The assistant will save things here automatically as you chat."*
4. Edit action opens a modal pre-populated with the entry's current `description` and `content` (from `GET /api/v1/rm-memory/{name}`). Save → `DELETE /{name}` → `POST /` with the new payload. Optimistic update in the list.
5. Delete action confirms (native confirm or modal) → `DELETE /{name}` → optimistic removal from the list.
6. Loading + error states match the admin/memory page pattern: spinner during fetch, red callout on error with the upstream `detail`.
7. Request-token guard (the same Bugbot finding from PR #59) on the list refresh: a stale response from a slow first fetch can't overwrite a fresh second fetch.
8. Sidebar has a new "Memory" entry routing to `/memory/user`. Active state matches the `(app)/admin` sidebar pattern.
9. New i18n keys go through `npm run i18n:parse` so all 60 locale JSONs include them — `Format CI` won't redder than it already is.
10. New unit/component tests:
    - API client: 4-6 tests over fetch shape, query-param encoding, error mapping (matching the existing `apis/admin/memory.ts` test style).
    - Component test on `MemoryPanel`: empty state, populated state, edit happy path, delete happy path, error banner.
11. The page works with the existing dev compose (`docker-compose.rm.yaml`) and the BFF env vars already wired (`MEMORY_GATEWAY_TOKEN`, `RM_MEMORY_MCP_URL`).

## Approach

- **API client (`src/lib/apis/rm-memory.ts`)** mirrors `apis/admin/memory.ts`. Four functions: `listMemories(token, opts?)`, `getMemory(token, name, opts?)`, `saveMemory(token, body)`, `forgetMemory(token, name, opts?)`. Each returns the typed Pydantic-shaped payload from the BFF. Use the same `error / caught` pattern from PR #59 to keep empty-string `detail`s from leaking as a successful response.
- **`MemoryPanel.svelte`** props: `{ scope: 'user' | 'project'; projectId?: string; token: string }`. Internally fetches the list, groups by `type`, renders rows. Same Tailwind shape as `admin/memory/+page.svelte` but list-oriented (one card per type, table inside).
- **`MemoryEntryRow.svelte`** is a presentational row + two icon buttons. Edit dispatches `openEdit(entry)`, delete dispatches `requestDelete(entry)`.
- **`EditMemoryModal.svelte`** lifts heavily from the existing `chat/Settings/Personalization/EditMemoryModal.svelte` pattern but talks to the rm-memory BFF instead of the native OpenWebUI memory API. It does the forget+save sequence and emits `saved` / `error`.
- **Optimistic update strategy:** on save, immediately patch the in-memory list with the new entry; on success of the network round-trip, no-op; on failure, refetch the full list and show the error. On delete, splice locally → call `DELETE` → on failure, refetch + error.
- **Provenance:** display `formatTimestamp(entry.updated_at)` only. Filed as a follow-up: extend MCP `list_memories` output to include `session_id` + `emitted_at` so the panel can show "learned from your chat on Tuesday at 14:32". Cross-repo work, not in this cycle.
- **Sidebar entry:** add to the existing user nav (probably `src/lib/components/layout/Sidebar/UserMenu.svelte` or wherever Workspace is registered — confirm during impl). Translation key `Memory`. Icon: book/note glyph from existing icon set, no new SVG.

## Not doing

- `/memory/project/[id]` route — no entry point in this chatbot; deferred.
- Cross-MCP provenance fields (`session_id`, `emitted_at`) — needs MCP-Servers change first.
- Bulk import / export — out of scope for #47.
- Graph view / dedup suggestions — mem0 has these; defer per #47.
- Memory creation from the panel (only edit/delete). The assistant creates entries; users can correct or delete them. `POST /api/v1/rm-memory` exists on the BFF and the modal can technically use it via a "New entry" button, but #47 frames this as a management surface, not an entry creator. Leaving the button out keeps scope clean — easy to add later if users ask.
- Native OpenWebUI memory UI changes (`chat/Settings/Personalization/ManageModal.svelte`). That's a separate, native memory store. We don't touch it; it keeps working as-is.

## Validation plan

1. Run `pytest backend/open_webui/test/util/test_rm_memory.py` to confirm BFF still green (regression guard, no BFF changes expected).
2. Add component tests under `src/lib/components/memory/` using vitest + Svelte testing — mirror the patterns in any existing `*.test.ts` next to components.
3. Manual smoke in the running dev compose: sign in, visit `/memory/user`, verify list renders for the seeded user; edit one entry; delete one entry; refresh and confirm persistence. Use the `e2e` skill if a clean automated check is needed.
4. Visual check matches admin/memory page styling (spacing, dark mode, mobile width).
5. Run `npm run i18n:parse` and confirm 60 JSON files updated; `Format Frontend` CI green on the PR.
