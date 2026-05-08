# Forge Spec: Admin memory adoption-stats — frontend route

**Cycle:** 3 | **Clock:** ~0.3h elapsed | **Size:** medium

## What

A new admin-only Svelte route at `/admin/memory` that calls cycle-2's BFF (`GET /api/v1/admin/memory/stats`) and renders the result as four cards: Entries (total + by_scope_and_type), BOPA sessions (total + active), Recent activity (recall/save/notes + by_tool error rates), Top users (top 10 by entry count). Adds a `1d / 7d / 30d / 90d` window selector and Refresh button. Adds a "Memory" tab to the admin nav.

## Why

Cycle 2 shipped the BFF; advisors and operators still can't see the data without curl. This route is what an admin opens to answer _"is anyone using memory yet?"_ in a glance — the entire reason for issue #48. Closes the loop on the BFF's user value and removes the SSH-and-curl detour that was the original pain.

## Success criteria

1. `/admin/memory` renders for admin role; non-admin gets bounced to `/` by the existing `(app)/admin/+layout.svelte` gate.
2. Production build emits `entries/pages/(app)/admin/memory/_page.svelte.js`.
3. All four cards render with sensible empty states ("No entries yet — the assistant will save them as users chat", "No BOPA sessions yet. Try `/bopa-haalbaarheid <adres>`", etc).
4. When BFF returns 503 with the `MEMORY_ADMIN_TOKEN not configured` detail, the page surfaces a one-line fix hint instead of a generic error.
5. Window selector (1d/7d/30d/90d) re-fetches; recall hit-rate computed from `recall.calls` and `recall.with_hits` (never divides by zero).
6. New "Memory" tab in admin nav (uses existing `Memory` i18n key already in all 60 locale JSONs).

## Approach

- Single page; no shared component yet (the user-facing memory panel #47 is separate scope).
- Tables for breakdowns; no charts. Time-series chart is out of scope until #75 (recorder) ships.
- API wrapper in `$lib/apis/admin/memory.ts` with TS types mirroring cycle-2's Pydantic models.
- Reuse `Spinner` + Tailwind utility classes already used elsewhere in admin/.
- The page handles its own auth fail-safe (`if ($user?.role !== 'admin') return;`) belt-and-braces with the layout gate.

## Not doing

- Bar chart for entries-by-scope/type — skip until the eye-test on prod tells us a bar is more readable than the table.
- Line chart for time-series — depends on MCP-Servers#75 (recorder), shippable later as an additive change.
- Per-user drill-down (clicking a row to see that user's entries) — that's #47 territory.
- Caching / SWR — admin loads this manually, no need for client cache.
