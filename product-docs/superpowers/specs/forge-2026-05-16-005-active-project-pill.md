# Forge Spec: Active-project pill in chat Navbar

**Cycle:** 6 | **Clock:** ~5h elapsed (day) | **Size:** small-medium

## What

A small Svelte component `ActiveProjectPill.svelte` that fetches `GET /api/v1/rm-memory/active-project?chat_id={$chatId}` and renders a one-line badge in the chat Navbar reading e.g. **`📂 Beleidsscan: Utrecht / energietransitie`** when a project is bound, or nothing at all when the chat has no project.

## Why

Yesterday's Memory PR #30 and today's Skills #14 and #114 together make the model silently bind chats to projects. Advisors currently have no way to tell whether their chat is project-scoped — so they can't trust that "save this finding" will land in the right project context. The pill makes that scoping visible without requiring the advisor to read tool calls.

## Success criteria

1. New file `src/lib/apis/rm-memory.ts` exposes `getActiveProject(token, chatId)` returning `ActiveProject | null` (mirrors admin/memory.ts patterns).
2. New component `src/lib/components/chat/ActiveProjectPill.svelte` renders the pill when an active project exists; renders nothing otherwise (collapses to zero-height).
3. Mounted in `Navbar.svelte` directly after the ModelSelector slot, on the same row.
4. Re-fetches when `$chatId` changes (reactive).
5. Fails silently on network/transport error — the chat doesn't break if the BFF is down.
6. Works on mobile (icon + project_id-without-prefix when label is missing) and desktop (icon + label + truncation past ~280px).
7. Click on the pill opens a tooltip or copies the canonical `project_id` to clipboard (small bonus, low-effort).

## Approach

- Use the existing `WEBUI_API_BASE_URL` + bearer-token pattern from `admin/memory.ts`.
- Use Svelte's `$:` reactive statement on `$chatId` to drive the fetch.
- Style with existing Tailwind classes; match the muted-pill aesthetic used elsewhere in the navbar (rounded-full, ring, bg-gray-50/dark:bg-gray-850, text-xs).
- Icon: a single emoji `📂` keeps it dependency-free; if there's a folder icon component nearby, use that instead.

## Not doing

- Pill click → switch-active-project UI (no `set_active_project` from frontend yet — the model is responsible for setting; the pill is read-only).
- Live SSE updates when the model calls `set_active_project` mid-chat — the pill refreshes on `$chatId` change for now. A short polling fallback could be added later if advisors notice the lag.
- Touching the admin memory dashboard.
- Frontend tests with Playwright — `vitest` component tests are fine; this is small.
