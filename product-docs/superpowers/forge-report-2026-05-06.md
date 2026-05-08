# Forge Report — 2026-05-06

**Wall clock:** ~30 min active build
**Cycles completed:** 4
**Features shipped:** 2 merged, 3 awaiting bot review

## Shipped Features

| #   | Feature                                  | PR  | Status                  | Issue closed | Size |
| --- | ---------------------------------------- | --- | ----------------------- | ------------ | ---- |
| 0   | /embed route for Geoportaal iframe panel | #54 | merged                  | #53          | M    |
| 1   | /bopa-omgevingsaspecten slash prompt     | #55 | merged                  | #44          | M    |
| 2   | Admin memory adoption-stats BFF          | #56 | open (bugbot pending)   | part of #48  | M    |
| 3   | Admin memory adoption-stats frontend     | #57 | open (stacked on #56)   | rest of #48  | M    |
| 4   | rm-memory user-facing list BFF           | #58 | open (stacked on #56)   | foundation for #47 | M    |

PR #54 was opened just before the forge run started. The remaining 4 are forge cycles 1–4.

## Impact

### New use cases enabled

- **Geoportaal iframe rendering** (#54). Geoportaal panel can now point at `/embed` instead of `/`, dropping the cramped full-app chrome inside a 400px iframe. Unblocks Geoportaal PR #1456.
- **BOPA Phase 4 in chat** (#55). Advisors can now run `/bopa-omgevingsaspecten` directly against an MCP-backed flow. The previous text "Fase 4–6 commando's nog niet gepubliceerd" is now only Fase 5–6.
- **One-glance memory adoption check** (#56 + #57). Admin opens `/admin/memory` and sees entries-by-scope/type, top-N users, recall hit rate, BOPA totals — instead of the old SSH-and-curl chore.

### Existing UX enriched

- **BOPA inlet next-step hint** auto-emits `/bopa-omgevingsaspecten` when an advisor's session has Phases 1+2+3 done (was: warning "MCP-tool nog niet beschikbaar").

### Infrastructure expanded

- **`backend/open_webui/utils/mcp_response.py`** — pure SSE-or-JSON parser + JSON-RPC envelope unwrapper, shared by both new admin/user BFFs. Direct mirror of the rm-tools filter-side parser; unifies the chatbot backend's MCP-client style.
- **Two new BFF patterns** — admin (gateway-bypassing, no `X-Forwarded-User`) and user (`X-Forwarded-User: <email>` + gateway token). Subsequent rm-memory CRUD endpoints can copy the user-side pattern verbatim.
- **`src/lib/utils/appBootstrap.ts`** — extracted store loaders out of `(app)/+layout.svelte` so `/embed` and `(app)` share one source of truth on what data Chat receives. Tightens consistency across surfaces.

## Unfinished / Next Session

| Priority | Feature                                  | Why                                                              | Est. size |
| -------- | ---------------------------------------- | ---------------------------------------------------------------- | --------- |
| 1        | Merge #56 / #57 / #58 once bugbot clears | All have local tests passing; review-pipeline gating only        | n/a       |
| 2        | rm-memory CRUD BFF (POST/DELETE)         | Cycle 4 is read-only; user-facing edit/forget needs the writes   | M         |
| 3        | User memory panel (#47, frontend)        | Read BFF is shipped; panel reads `/api/v1/rm-memory/list`        | M-L       |
| 4        | BOPA Phase 5/6 (chatbot side, #45/#46)   | Blocked on MCP-Servers#73/#74 (`save_onderbouwing_section`, `score_onderbouwing`). Could ship the MCP tools first cross-repo | L         |
| 5        | #51 tool-call failure surfacing (model-side) | Prompt-side landed on PR #52; Gemini doesn't yet honor it. Needs deeper model-side guard or output-postprocess | M         |

## Observations

### What went well

- **Pattern reuse compounded.** Cycles 2/3/4 leaned on the same SSE-parser + Pydantic-typed BFF + httpx-mocked-test recipe. Each cycle ended in 6–10 minutes of build time because the work was ~80% template, ~20% novelty.
- **Stacked PRs kept diffs honest.** PR #57 stacked on #56, PR #58 stacked on #56 — each PR shows only its own delta in the GitHub UI instead of cycle-2's BFF being repeated three times.
- **Spec-then-build discipline.** Writing the forge spec before touching code surfaced the right scope-cuts every cycle (e.g. cycle 2 = backend only, frontend = cycle 3; cycle 4 = read-only, CRUD = future).

### What took longer than expected

- **Pre-existing format debt.** Cycle 2's `Format Backend` failed on 7 files; only 1 was mine. Same on cycle 1's frontend (single emphasis-style nit in the spec). Both are documented in `project_ci_format_debt.md` — not caused by this session, but each costs one extra round-trip commit.
- **Cross-branch import ordering.** Stacked PRs hit a merge conflict in `main.py` because cycle 4 added `rm_memory` to the same import list cycle 2 added `admin_memory` to. Resolved by hand; alphabetical-only auto-sort would have handled it.

### What patterns emerged

- **The "MCP BFF" recipe is now stable**: gateway/admin token, optional X-Forwarded-User, SSE-or-JSON parser, Pydantic response model mirroring the MCP TS interface, 9-10 unit tests covering happy + 4 failure modes + token-config guards. Future MCP exposures (rm-databank policy search, rm-geoportaal spatial constraints) should drop straight into this template.
- **Cycle splitting beats cycle bundling.** The original #48 was "ship the admin stats view" — bundling backend + frontend in one cycle would have been a Large feature. Splitting into BFF (cycle 2) + frontend (cycle 3) gave each piece its own observable success criterion and let cycle 2 ship even though the frontend lagged review.

## Pause rationale

Last 4 cycles all touched memory/admin BFF territory — that's the "circling the same area" drift signal forge calls out. Three open PRs in a dependent stack means the merge pipeline needs bugbot time to catch up before continuing makes sense; stacking a 5th cycle on top before #56 lands compounds the rebase blast-radius if any of the queued PRs needs revisions.

Natural resume points next session: clear the merge queue (1 → done), then either continue rm-memory toward CRUD + panel (2/3) or pivot to BOPA Phase 5/6 cross-repo (4).
