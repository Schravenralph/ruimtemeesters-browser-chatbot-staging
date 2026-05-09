# ADR-0014: RM-Memory implementation engine

**Date:** 2026-05-08
**Status:** Accepted

## Context

ADR-0013 committed to RM-Memory with a four-scope model (User / Project / Brand / Global) under an MCP-first capability strategy. It deliberately left the _engine_ question open — the principle was decided, but how RM-Memory actually gets built was tracked as a follow-up.

This ADR closes that follow-up.

The session walked through a long arc on this question. Initial direction was "fork Hindsight." That direction softened as we identified:

- Hindsight's value sits in _prose-extraction_ and _multi-strategy retrieval_ — capabilities that solve problems we don't yet have at our scale (handful of users, ~hundreds of memories at most)
- Cross-surface memory continuity is already solved by the iframe + service-pattern architecture (ADR-0011 / ADR-0012) — both share OpenWebUI's backend, so no external memory hub is required to make sibling apps see the same memory
- Structured project state (BOPA sessions, typed entities) belongs in our existing typed MCP, not in any prose-extraction tool
- We already have ~80% of the engine in `@rm-mcp/memory` (per ADR-0002 in the MCP-Servers repo): identity model, three-scope predicate, FTS, tombstones, session-events provenance, BFF, filter inlet, admin stats

Given that, the engine question is essentially: keep building on what we have, or replace it with Hindsight (which would force us to migrate scope semantics, identity, BFF, admin stats, BOPA glue, and Dutch-language search onto Hindsight's primitives).

## Considered options

### (a) Extend `@rm-mcp/memory`

Take the existing package, add the `brand` scope tier, ship.

What changes concretely:

- Migration: add `brand` to the scope check constraint; add `owner_org_id` (NOT NULL on `brand` rows, NULL elsewhere); update the partial read-predicate index for `brand` lookups
- Read predicate: extend to four branches per ADR-0013 §2
- `save_memory`: accept `scope='brand'`; enforce `scope='brand' ↔ owner_org_id` in a model validator (mirroring the existing `scope='project' ↔ project_id` check)
- BFF (`backend/open_webui/routers/rm_memory.py`): expand the `SCOPE` literal type
- Filter inlet: no change — read predicate is server-side
- UI (when the panel is built): one new scope badge label
- Skill (memory authoring guide, next ADR): teach the model when to save under each scope

Total: roughly a week of focused work end-to-end with tests. The largest line-count is the migration + tests; the predicate change is ~5 lines.

**Pros:**

- Smallest blast radius
- Preserves existing investment (BFF, filter inlet, admin stats, BOPA-session state, Dutch FTS, identity model)
- No data migration
- No new operational surface to monitor
- Works with our existing skill/tooling

**Cons:**

- We don't get Hindsight's extraction, multi-strategy retrieval, mental models, or cross-encoder reranking
- FTS-only retrieval will eventually hit a quality ceiling (probably at thousands-of-memories scale we don't have yet)
- Drift / dedup remain unaddressed in v1 of RM-Memory (same as today)

### (b) Fork Hindsight as RM-Memory

Take Hindsight upstream, fork it as `Schravenralph/Ruimtemeesters-Memory`, customise to host the four-scope model.

What changes concretely:

- Map our `clerk:<email>` identity onto Hindsight's tagging / namespace primitives
- Layer four-scope semantics over Hindsight's existing model — likely as tag prefixes (`scope:user:<id>`, `scope:project:<pid>`, `scope:brand:<oid>`, `scope:global`)
- Rewrite the BFF (`rm_memory.py`) to call Hindsight's API instead of our MCP
- Re-implement the admin adoption-stats endpoint against Hindsight's data model
- Migrate existing memory data via Hindsight's `retain` endpoint (LLM extraction will reshape the data — round-trip is lossy)
- Validate Dutch-language behaviour — Hindsight uses BM25; the dictionary handling for Dutch stems may need a fork-side patch
- Update the filter inlet (`memory_recall_context.py`) to call Hindsight's `recall` instead of our MCP
- Update the skill / tool documentation for the new tool names (`retain` / `recall` / `reflect` / `mental_models` instead of our save / recall / list / forget)
- Stand up Hindsight's compose service alongside the chatbot stack
- Establish ongoing upstream sync routine

Hindsight's capabilities we'd inherit:

- Multi-strategy retrieval (semantic + BM25 + entity-graph + temporal) with cross-encoder rerank
- LLM-driven entity extraction on `retain` calls
- Mental Models (auto-refreshing summaries)
- 91.4% LongMemEval per their published number

**Pros:**

- Significantly more capable engine for retrieval and dedup
- Anticipates problems we'd otherwise have to build solutions for ourselves (entity resolution, drift handling)
- The fork itself is free (MIT license) — branding work is small

**Cons:**

- Weeks-to-months of integration work
- Lossy migration of existing memory data (extraction reshapes things)
- Loses our typed scoping primitives — they get re-expressed as tags, with the predicate enforcement moving from Postgres CHECK constraints to application-level conventions
- Loses our Dutch tsvector behaviour (gain BM25 + embeddings, but the Dutch story needs validation)
- BOPA-session state stays in `@rm-mcp/memory` regardless, so we don't get to retire that package — we end up running both
- Ongoing fork-sync chore against an actively-developed upstream
- Building capability we may not exercise at our current scale

### (c) Greenfield

Build from scratch — neither extending `@rm-mcp/memory` nor forking Hindsight. Take Hindsight's design ideas (multi-strategy retrieval, mental models, autoDream consolidation) and reimplement them on our schema.

**Pros:**

- Maximum control
- No upstream-fork chore

**Cons:**

- Months of work
- We'd be writing what Hindsight already wrote, badly, slower
- Justified only if both (a) and (b) fail — and they don't

Rejected without further consideration.

## Decision

**Option (a): extend `@rm-mcp/memory` with the four-scope model.**

This is the YAGNI call the rest of this session has been making. We have the engine; we add a tier; we ship; we earn upgrades when pain shows up.

The argument for (b) is real but premature for our scale. Hindsight's strengths are answers to questions we haven't been asking: thousands of memories with FTS recall starting to miss; LLM-extracted facts replacing manually-saved ones; entity drift across long-running corpora. We're not there. When we are, (b) becomes a clean migration target — the four-scope semantics from this ADR map cleanly onto Hindsight's tag primitives, and the BFF adapter is the lift we'd take.

## What this commits to concretely

Order of work (each is a self-contained PR-sized chunk):

1. **Migration `006_brand_scope_and_approval.sql`** in `Ruimtemeesters-MCP-Servers/packages/memory/migrations/`:
   - Add `'brand'` to the scope check constraint
   - Add `owner_org_id TEXT REFERENCES memory.orgs(id)` (NOT NULL on `brand` rows, NULL elsewhere — enforced by CHECK)
   - Add `status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending','rejected'))`
   - Add CHECK constraint: `type != 'session-summary' OR scope = 'user'` — session-summary is user-scope only (per the brainstorm rule: sessions are personal, project/brand/global have stricter information governance than chat-log dumps)
   - Update partial indexes: existing live-read index also filters `status='active'`; new partial index for the admin pending queue
   - Update read predicate to extend to four scopes per ADR-0013, AND filter `status='active'` outside admin/owner-of-pending lookups

2. **Tool updates** in `packages/memory/src/tools/`:
   - `saveMemory` accepts `scope='brand'`; enforces `scope='brand' ↔ owner_org_id` and `scope='project' ↔ project_id` invariants; **infers `status` from scope: `user` → `active`, others → `pending`** (caller doesn't choose)
   - `saveMemory` rejects `type='session-summary'` for any scope other than `user` (mirror of the DB CHECK; fail fast at the tool boundary)
   - `recallMemory` / `listMemories` / `getMemory` filter `status='active'` by default; new admin-only `listPendingMemories` exposes the queue
   - New admin-only `approveMemory(id)` and `rejectMemory(id, reason?)` tools; both audit-log to `memory.session_events`
   - `forgetMemory` works on active rows only (pending rows die via reject, not forget)

3. **BFF update** in `backend/open_webui/routers/rm_memory.py`:
   - Expand `SCOPE` literal to include `brand`
   - Surface `status` in the `MemoryEntry` model (so the panel can show pending state)
   - New endpoint `GET /api/v1/rm-memory/pending` for the user's own pending project memories (so they can approve their own)
   - New endpoint `POST /api/v1/rm-memory/{name}/approve` and `/reject` (gated to the right caller — user for project memories they own, admin for brand/global)
   - Admin routes (already in `admin_memory.py`): pending list across all users, approve/reject for brand/global

4. **Filter changes** in `rm-tools/filters/`:
   - `memory_recall_context.py` — no logic change; brand-scope rows flow automatically once the MCP serves them
   - **New** `memory_pending_notice.py` (filter outlet) — when the active user has pending memories awaiting their approval, append a one-line note to the assistant response: _"(You have N pending memories awaiting your approval — review them in the memory panel.)"_ Cheap, throttled (e.g. once per N turns), respects user opt-out

5. **UI work** (separate cycle — not part of the migration PR):
   - Memory panel surfaces pending status, with inline approve/reject buttons for the user's own project memories
   - Admin memory page gets a "Pending Approval" tab listing brand + global candidates with approve/reject + reason
   - Both pages are extensions of pages we already have — not new surfaces

6. **Memory authoring guide** (skill, `packages/memory/skills/memory.md`) — written separately (Task #2, scheduled for after this engine ADR settles)

7. **MCP-Servers ADR-0002 cross-reference** — note the four-scope refinement + approval workflow point at this ADR

Out of scope of this ADR (deliberate):

- No drift / dedup pass yet — defer until felt
- No retrieval upgrade (we keep tsvector FTS) — defer until felt
- No data migration — existing rows default to `status='active'` so they keep working; new `brand`-scope rows are authored under the new workflow from day one
- No bulk-approve / batch-reject UI — basic per-row approve/reject only in v1

## Triggers to flip to (b)

Concrete signals that would justify migrating to a Hindsight fork:

1. **FTS recall quality complaints.** Users reporting "the chatbot didn't surface a memory I know is there." Once we hear this from multiple users on multiple queries, multi-strategy retrieval becomes worth its weight.
2. **Memory count crosses ~2000 per user.** At that scale FTS rank quality typically degrades; embedding-based retrieval starts to dominate.
3. **Drift becomes a felt problem.** Same fact saved under multiple names; wrong facts compounding via recall. Mental Models or autoDream-style consolidation passes start being earned.
4. **Cross-encoder rerank produces measurably better results in an A/B.** If we're motivated to run that experiment at all, we're likely already at a scale that justifies (b).
5. **Implementation cost of ad-hoc patches to `@rm-mcp/memory` exceeds the cost of a Hindsight migration.** This is the meta-trigger — when we're spending more time building Hindsight features into our package than it would cost to adopt Hindsight, it's time.

When any of these fires, this ADR gets revised: we add a "Migration plan to Hindsight" section, scope it as a multi-cycle project, and run it.

## Consequences

**Positive:**

- Engine question is settled with the smallest committed work
- The four-scope model ships fast — brand scope becomes available for memory authoring soon
- Existing investment is preserved
- The (b) option stays cleanly on the table for a future inflection point — this ADR captures the trigger conditions explicitly so we don't re-litigate from scratch

**Negative:**

- We accept current FTS-recall behaviour and the absence of drift/dedup machinery for the foreseeable future
- Hindsight's marketing-published 91.4% LongMemEval gap stays a gap until/unless (b) triggers
- We continue to pay the small ongoing tax of "rolling our own" on a category where opinionated platforms exist

## Related ADRs

- **ADR-0002** (MCP-Servers repo) — Original three-scope memory architecture. This ADR commits to extending it; the migration in §"What this commits to concretely" §1 is the implementation
- **ADR-0011** — Service-pattern AI surfaces — Geoportaal's custom UI will read from RM-Memory under the four-scope predicate
- **ADR-0012** — Frontend strategy — preserves OpenWebUI investment; this ADR continues the same posture for the memory engine
- **ADR-0013** — MCP-first capability strategy + RM-Memory four-scope model — parent decision; this ADR is its implementation choice

## Follow-up work

- **Migration 006 + tool updates** (engine work) — sized as one cycle each, sequenced
- **Memory authoring guide** (Task #2 in the session todo list) — depends on this ADR being settled, scheduled next
- **rm-skills MCP design** (Task #3) — depends on Task #2 being settled, scheduled after
- **MCP-Servers ADR-0002 cross-reference update** — small doc touch, can land alongside migration 006
