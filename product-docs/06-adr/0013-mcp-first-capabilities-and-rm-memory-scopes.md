# ADR-0013: MCP-first capability strategy + RM-Memory four-scope model

**Date:** 2026-05-08
**Status:** Accepted

## Context

Two related commitments coming out of the 2026-05-08 architecture session:

1. **Capability layering.** ADR-0012 deferred the Anthropic-native pipeline (Skills, Memory tool, etc.). That means there are capabilities the model cannot reach via Anthropic primitives in our current setup. We need an explicit principle for _how those capabilities get expressed_ until the Pipe arrives.

2. **Memory scoping.** ADR-0002 (in `Ruimtemeesters-MCP-Servers/docs/adr/0002-memory-architecture.md`) established a three-value scope model: `user`, `project`, `global`. After working through the pipeline questions in this session — what gets saved, where it lives, who can see it — the three-value model is too coarse: there's no shape for "facts that apply to everyone at Ruimtemeesters but aren't universal truths." That gap matters because brand voice, RM-specific conventions, and shared procedural knowledge all live there.

This ADR records the principle and the refined scope model.

## Decisions

### 1. MCP-first capability strategy

**For any capability we want the chatbot to have that is NOT directly enabled by Anthropic Skills (or, today, anything we'd hypothetically gain from a Pipe), the carrier is an MCP tool.**

Concretely:

- New capability ideas → expressed as MCP tool surfaces (read tools, write tools, or both)
- The model invokes them via the existing tool-call mechanism that OpenWebUI's OpenAI-compat path already supports
- Works across every model provider, not just Claude
- Composes with our existing MCP ecosystem (rm-databank, rm-geoportaal, rm-state, rm-memory, etc.)
- No backend pipeline rewrite required to add new capabilities

This is the load-bearing trade we make to defer the Anthropic Pipe (per ADR-0012 §2). The cost: capabilities expressed as MCP tools cost an extra tool-call round-trip vs. native Anthropic primitives, and the catalog isn't progressively-loaded the way Anthropic Skills would be. The benefit: capability shipping doesn't block on the Pipe; we get to keep adding things.

Examples of capabilities we'd express MCP-first under this principle:

- **Procedural skills** (the "Skills" semantic): `list_skills`, `get_skill(name)`, `save_skill(name, description, content)` — same pattern as memory, just for procedural bundles
- **Memory** (this ADR §2): `recall_memory`, `save_memory`, `forget_memory`, `list_memories` — already exists in `@rm-mcp/memory`
- **Domain-specific tools** (already done): bouwvlak checks, BOPA session state, policy lookups — each its own MCP

The rule isn't "MCP for everything forever." It's "MCP for everything we can't get from Skills, until the Pipe ships and gives us native primitives." When the Pipe arrives, we'll likely keep most things as MCP (it's the cleaner abstraction) and selectively promote ones where progressive loading actually matters.

### 2. RM-Memory: four-scope model

We commit to building **RM-Memory** as the durable memory layer for the chatbot and (eventually) sibling surfaces. RM-Memory has **four scope tiers**, refining ADR-0002's three:

| Scope       | Visible to                             | Example                                                                                                                |
| ----------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **User**    | Only the owning user                   | "I prefer concise responses", "I'm an advisor specialising in archeologie"                                             |
| **Project** | Anyone with access to that project     | "This BOPA used Utrecht conventions", "Last time we ran the AERIUS calc, X happened"                                   |
| **Brand**   | Everyone at Ruimtemeesters (org-wide)  | "RM cites Lycens precedent first", "Our standard BOPA template structure is …", "Default report tone is direct, Dutch" |
| **Global**  | Universally readable, even across orgs | "Phase 5 of a BOPA is the onderbouwing", "DSO is the Digitaal Stelsel Omgevingswet"                                    |

The new tier is **Brand**. It's the one ADR-0002 implicitly missed because the read predicate was "any authenticated caller" for both project and global — fine for one-org-and-everyone-else-public, but it conflated org-internal conventions with universal facts. Splitting them gives us:

- A natural home for RM-specific conventions that survive across users and projects but shouldn't leak to public/global readers
- A working multi-org story without rewriting the schema later — `brand` is `org-scoped`, generalising to "the caller's org" when a second org ever lands
- A clearer mental model when authoring memories: "is this just me, this project, my company, or a fact the world knows?"

ADR-0002's read predicate generalises to:

```sql
WHERE (scope = 'user'    AND owner_user_id = :caller)
   OR (scope = 'project' AND project_visible_to(:caller, project_id))
   OR (scope = 'brand'   AND owner_org_id = :caller_org)
   OR (scope = 'global')
```

Which preserves ADR-0002's "tightening is a query diff, not a migration" property — adding a second org just means populating `:caller_org` correctly, not changing schema or data.

### 3. Implementation engine — open

This ADR commits to _what_ RM-Memory is (the four-scope model and the MCP-first principle), not _how_ it's built. Three implementation paths remain open:

- **(a) Extend the existing `@rm-mcp/memory` package.** Already implements the three-scope model from ADR-0002, has the BFF + filter inlets + admin stats wired in. Adding `brand` is additive: one schema change, one read-predicate update, one UI label. Lowest blast radius.
- **(b) Fork Hindsight, brand it RM-Memory, extend with the four-scope model.** Bigger commitment, more capability (entity extraction, multi-strategy retrieval, mental models), but requires migrating data and adapting Hindsight's tagging/namespace model to our scope semantics. The fork-vs-vendor-vs-wrap conversation from earlier in this session applies.
- **(c) Greenfield build on Hindsight's design ideas without forking.** Most expensive option; not justified unless (a) and (b) both fail.

Engine choice is a deliberate next decision and gets its own ADR (likely the next-numbered one) once we've sized the gap between option (a)'s capabilities and what we actually need.

## Rationale

**Why MCP-first, not waiting for Pipe:**

- Pipe is months of work and pushes against ADR-0012's "preserve OWUI investment" principle
- MCP works today, against any model, with our existing infrastructure
- The cost of MCP-vs-Skills (extra tool round-trip, no progressive loading) is small compared to the cost of building and maintaining a Pipe
- When the Pipe eventually arrives, the MCP capabilities we shipped don't go away — they keep working alongside whatever native primitives we add

**Why a four-scope memory model:**

- Three scopes conflated "RM-internal conventions" with "universal facts." Adding brand fixes this without breaking the existing predicate shape
- Brand is the scope that's most useful and most missing — most of what we'd want to remember about Ruimtemeesters as an organisation lives there
- Multi-org future is preserved by making brand explicit (`owner_org_id`) rather than implicit ("any authenticated caller")
- The cognitive load on memory authors is small — four levels with clear examples is easy to teach the model and easy for users to manage

## Consequences

**Positive:**

- New capabilities ship without blocking on the Pipe decision
- Memory has a real home for RM-internal conventions, which today either don't get saved or pollute the global scope
- Engine choice for RM-Memory (a vs b vs c) becomes a clean next decision rather than entangled with the principle decision
- Multi-org future is one schema migration away, not a rewrite

**Negative:**

- MCP-first capabilities cost an extra round-trip per invocation. Latency-sensitive flows might feel it
- Brand scope adds one more concept to teach the model and explain to users — "what goes in brand vs global" will need clear authoring guidance in the memory skill
- Until the implementation engine ADR lands, RM-Memory is conceptually defined but not yet built — risk of decision drift if we leave it open too long
- ADR-0002 in MCP-Servers needs an updated reference to this ADR; the three-scope model there is now superseded

## Triggers to revisit

- Latency or token cost from MCP-routed capabilities exceeds projections → §1 (consider promoting some to Pipe natives)
- Brand scope turns out to be poorly used or confusing in practice → §2 (collapse back to three scopes or split further)
- A second org actually lands → re-validate the read predicate generalisation works as designed

## Related ADRs

- **ADR-0002** (MCP-Servers repo) — Original three-scope memory architecture. This ADR refines its scope model from three to four; the read predicate generalisation in §2 is the load-bearing change. Cross-reference should be added in MCP-Servers.
- **ADR-0007** — Multi-surface platform — RM-Memory is one of the resources sibling apps will read via MCP
- **ADR-0011** — Service-pattern AI surfaces — When Geoportaal's custom UI eventually surfaces memory entries (e.g. "user previously noted X about this project"), it pulls from RM-Memory under the four-scope predicate
- **ADR-0012** — Frontend strategy — The Pipe deferral in 0012 §2 is the load-bearing reason MCP-first exists in this ADR

## Follow-up work tracked separately

- **Engine ADR** (settled 2026-05-08): see ADR-0014. Implementation path (a) — extend `@rm-mcp/memory` with the four-scope model and approval workflow.
- **Memory authoring guide** (settled 2026-05-08): authored at `Ruimtemeesters-MCP-Servers/packages/memory/skills/memory.md`. See §3 below for the delivery-mechanism decision.
- **MCP-Servers ADR-0002 cross-reference**: add a "Superseded by Browser-Chatbot ADR-0013 (four-scope refinement)" note.
- **rm-skills MCP** (the procedural-knowledge sibling, mentioned in §1): scope and build under the MCP-first principle. In progress as Task #3 in the 2026-05-08 session.

## 3. Memory authoring guide delivery mechanism (decided 2026-05-08)

The authoring guide written under §2 needs to reach the LLM somehow. Four delivery options were on the table:

| Option                             | Mechanism                                                                                                           | Trade-off                                                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **(a)** Static skill file          | `packages/memory/skills/memory.md`, loaded into system prompt at session start (same pattern as existing `bopa.md`) | Always in context; modest token cost; no per-tool-call freshness |
| (b) ADR / doc only                 | Lives in `product-docs/` for humans                                                                                 | Doesn't reach the model — rejected                               |
| (c) MCP-loaded on every tool call  | Tool description includes the criteria, or a separate MCP fetch on each save                                        | Always fresh; per-call latency; more tool surface                |
| (d) Database row of type=reference | Loaded dynamically via recall                                                                                       | Couples the guide to memory data; rejected as over-clever        |

**Decision: (a) — static skill file.** Mirrors the existing `bopa.md` pattern, gets the criteria into the model's view at every session start, and avoids per-tool-call latency. Token cost is modest (the skill file is a few KB).

**Escalation trigger to (c):** if static loading proves insufficient — specifically if (i) token-budget pressure from accumulated skill files becomes a measurable problem, (ii) the model fails to apply the criteria reliably across sessions, or (iii) we need to update the criteria and want changes to propagate without re-loading sessions — migrate to MCP-loaded-on-every-relevant-tool-call. The escalation path involves: re-host the authoring guide as content the `save_memory` tool description references (or a separate `get_memory_authoring_guide` tool); accept the per-call latency cost in exchange for always-fresh criteria and zero static system-prompt overhead.

This escalation is recorded here so it doesn't need to be re-discovered. If we hit one of (i)/(ii)/(iii), we revise this ADR section with a "switched to (c) on YYYY-MM-DD because…" note and execute the migration.
