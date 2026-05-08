# ADR-0015: rm-skills — User skills (DB) + Company skills (files)

**Date:** 2026-05-08
**Status:** Accepted

## Context

ADR-0013 §1 named `rm-skills` as the procedural-knowledge sibling to RM-Memory under the MCP-first capability strategy. The 2026-05-08 brainstorm went through several design iterations — initially mirroring RM-Memory's four-scope + approval-workflow shape — before landing on a deliberately simpler model.

Two observations drove the simplification:

1. **Skills don't need an approval queue.** Memories need pending/approve because the model can auto-save. Skills (per the v1 save policy) are explicit-ask-only — by the time `save_skill` is called, a human has already authorised it. A queue solves a problem that doesn't exist here.

2. **The scope axis collapses for skills.** Memories have four scopes because they distill observations across personal / project / org / universal layers. Skills don't behave that way — most skills are either *one user's personal procedure* (User) or *organisation-wide canonical procedure* (Company). Project-scoped skills and Global skills both turned out to be edge cases nobody concretely needed.

This ADR records the simplified design.

## Decisions

### 1. Two skill sources

Skills come from exactly two places:

| Source | Storage | Mutability | Authored by |
|---|---|---|---|
| **User skills** | `memory.skills` table (Postgres) | Fully mutable by the owner | The owning user (via the chatbot or panel) |
| **Company skills** | Markdown files in `Ruimtemeesters-MCP-Servers/packages/memory/skills/company/` (repo) | **Immutable at runtime** — modified only via PR review | Ruimtemeesters as an organisation, via source control |

This mirrors the way Anthropic's "superpowers" (the bundled Claude Code skills like `init`, `security-review`) work: shipped as files, version controlled, never touched at runtime by any caller. User skills are the additional layer the user owns.

The existing skill files `packages/memory/skills/bopa.md` and `packages/memory/skills/memory.md` (the rm-memory authoring guide) are the first two Company skills under this model. We're formalising existing practice, not inventing a new category.

### 2. Schema for User skills

The `memory.skills` table holds **only** User skills. No scope column, no project_id, no owner_org_id, no status. Just:

| Column | Purpose |
|---|---|
| `id UUID PK` | Stable identifier |
| `owner_user_id TEXT NOT NULL REFERENCES memory.users(id)` | Owner — sole reader and writer |
| `name TEXT NOT NULL` | Stable identifier (lowercase-dashes, ≤120 chars) |
| `description TEXT NOT NULL` | One-line catalog entry (≤200 chars) |
| `body_md TEXT NOT NULL` | Human-readable procedure (markdown, ≤65 KB) |
| `steps JSONB NOT NULL DEFAULT '[]'` | Optional structured steps: `[{description, expected_output, tool_calls?}]` |
| `examples JSONB NOT NULL DEFAULT '[]'` | Optional input/output illustrations |
| `parameters_shape JSONB` | Optional JSON Schema for typed inputs (forward-looking, see "Out of scope") |
| `requires_tools TEXT[] NOT NULL DEFAULT '{}'` | MCP tool names the skill expects to be available |
| `created_at`, `updated_at`, `deleted_at` | Timestamps + tombstone |
| `session_id`, `emitted_at` | Provenance from the conversation that authored the skill |

Upsert key: `UNIQUE (owner_user_id, name)` — the user's namespace is theirs alone.

No FTS index. Skills are catalog-retrieved by name, not searched by query.

No approval workflow. The owner has total control over their own skills.

### 3. Company skill format

Company skills live as markdown files at `packages/memory/skills/company/<name>.md` with frontmatter for structure:

```markdown
---
name: bopa-phase-5-writing
description: How to draft Phase 5 onderbouwing sections, with step ordering and Lycens precedent priority
requires_tools:
  - rm-state.create_bopa_session
  - rm-databank.policy_search
parameters_shape:
  type: object
  properties:
    project_id: { type: integer }
    section_key: { type: string, pattern: "^[0-9]+(\\.[0-9]+)*$" }
  required: [project_id, section_key]
---

# How to write a BOPA Phase 5 section

[procedure body in markdown]

## Steps
1. ...
2. ...

## Examples
...
```

The MCP loads these files at startup, parses frontmatter into the same structural fields the DB columns hold (so `list_skills` can return User and Company skills under the same shape), and caches them in memory.

Reload happens on MCP server restart. There is no runtime mutation path for Company skills — by design.

### 4. Tool surface — three tools

| Tool | Purpose | Operates on |
|---|---|---|
| `list_skills()` | Returns the full catalog: `{name, description, source, requires_tools[]}[]` where `source ∈ {'user', 'company'}` | Both sources, merged |
| `get_skill(name, source?)` | Returns one skill with full body + structured fields. `source` disambiguates if a user has a personal skill with the same name as a company skill (rare; user shadow wins by default) | Both sources |
| `save_skill({name, description, body_md, steps?, examples?, parameters_shape?, requires_tools?})` | Upsert into `memory.skills` for the calling user. Cannot write Company skills | User skills only |
| `forget_skill(name)` | Tombstone the user's own skill (same semantics as `forget_memory`) | User skills only |

That's it. No admin tools, no approval tools, no scope variants. The caller's identity (the one user) determines what they can write to. Company skills require a PR — there is no MCP write path.

If a user calls `save_skill` with a name that collides with a Company skill, the user's version "shadows" the company one in their own catalog (visible only to them), and the company version remains untouched. The `source` field on `list_skills` makes the shadow visible.

### 5. Catalog filter inlet — `memory_skills_index.py`

Same as designed in the original brainstorm: every user turn (cached), top-30, Dutch label, name + description + source. Source distinguishes:

```
BESCHIKBARE SKILLS:
- `bopa-phase-5-writing` (company): How to draft Phase 5 onderbouwing sections...
- `prefers-concise-reports` (user): Personal report formatting preference
- `lycens-precedent-citation` (company): When and how to cite Lycens precedents
Roep `get_skill({name})` aan voor de volledige inhoud.
```

Sort order: User skills first (most specific to caller), then Company skills, then by recency. Token budget cap unchanged at 30 skills (~1K tokens).

### 6. Save-from-conversation UX

Unchanged from the original brainstorm: explicit user ask only for v1 (*"make this a skill called X"*). The model summarises the conversation into the skill body + structured fields, calls `save_skill`. No scope decision needed (always User; it's the user's table). No approval (the user is the owner).

Auto-detection of recurring workflows and post-success suggestions deferred to v2.

### 7. Token-bloat trigger — revisit at ~50 user skills + ~20 company skills

The catalog approach scales linearly. With User+Company combined cap at 30 surfaced (per §5), system prompt overhead is ~1K tokens. We revisit if total available skills per caller crosses ~70 (the catalog can't show all → relevance ranking starts mattering).

Options at that point: FTS-scored catalog, scope-prioritised loading, or migration to MCP-loaded-on-tool-call (per ADR-0013 §3 escalation pattern, generalised).

## What's intentionally absent

This is a deliberately simple design. The things missing vs. memory infrastructure:

- **No four-scope model.** Skills are User or Company, period. Project-scoped or Brand-scoped or Global-scoped skills aren't a thing here.
- **No approval workflow.** No `pending`, no admin queue, no approve/reject. User skills are self-managed; Company skills are PR-managed.
- **No admin tooling for skills.** Admins manage Company skills the same way they manage source code: `git`, code review, deploy.
- **No `owner_org_id`.** Brand-equivalent skills exist, but they're Company skills (in files), so the relationship is implicit ("the org owns the repo, the repo owns the company skills").
- **No status column.** No tombstone-with-status either; just `deleted_at` for the owner's own forgets.

These are real reductions in capability vs. the original brainstorm shape. Worth recording explicitly so future-us doesn't re-invent them. Triggers for re-introducing any of these are listed under "Triggers to revisit".

## What this commits to concretely

Order of work:

1. **Migration `007_user_skills.sql`** in `packages/memory/migrations/` — create `memory.skills` table with the columns above, upsert + live indexes (no FTS).
2. **Company skill loader** in `packages/memory/src/skills/companyLoader.ts` — read all `.md` files from `packages/memory/skills/company/` at MCP startup, parse frontmatter + body, cache in memory. Reload on SIGHUP optional v2.
3. **Bootstrap company skills** — move the existing `packages/memory/skills/bopa.md` and `packages/memory/skills/memory.md` into `packages/memory/skills/company/` and add their frontmatter. They become the first two Company skills.
4. **Tool implementations** in `packages/memory/src/tools/skills/` — `listSkills`, `getSkill`, `saveSkill`, `forgetSkill`. Tool descriptions distinguish User vs Company semantics in their copy.
5. **Server registration** in `packages/memory/src/server.ts` — register the four tools.
6. **BFF endpoints** in `backend/open_webui/routers/rm_skills.py` (new file) — proxy the user-facing tools.
7. **Filter inlet** `rm-tools/filters/memory_skills_index.py` — implements catalog injection per §5.
8. **Skill panel UI** — extension of the memory panel (User skills only, since Company skills aren't user-editable). Separate cycle.

## Out of scope

- **Executable skills** — `parameters_shape` and `requires_tools` are forward-looking. v1 doesn't auto-execute. Skills are read by the model, not run by an engine. Auto-execution is a future capability that builds on these fields.
- **Skill versioning history** — single-row upsert per `(owner, name)` for User skills; git history for Company skills. If we want User-skill version history later, that's a `memory.skill_versions` follow-on.
- **User skill sharing** — User skills are private to the owner. If a user wants their workflow shared org-wide, the path is "PR it as a Company skill" (via an admin). No mid-tier sharing.
- **Importing Anthropic SKILL.md format** — interesting but not in v1; if we ever ship the Anthropic Pipe (per ADR-0012), a converter between our frontmatter and Anthropic's format becomes a small mapping layer.

## Triggers to revisit

- **Project-scoped or Brand-scoped skills become a felt need.** Not just imagined — real cases where "a skill that applies to one project" or "a skill all RM advisors share but isn't right for the company-skill repo" appears. At that point we revisit and likely add scopes.
- **A user skill needs to graduate to a Company skill.** v1 path: PR. If this becomes routine and PRs feel heavy, consider a "promote to company" flow (admin-only command that copies a User skill into the file repo). Worth waiting for the third or fourth occurrence before building this.
- **Company-skill reload-without-restart becomes important.** v1 reloads only on MCP restart. If iteration on Company skills picks up, add a SIGHUP handler or a `/admin/skills/reload` endpoint.
- **`requires_tools` becomes a reliability problem.** Skills that reference tools the chatbot doesn't have available could surface confusing failures. Consider adding a startup-time validation that warns if any Company skill references a tool not registered.

## Consequences

**Positive:**

- Design fits in one page mentally — User vs Company, two storage tiers, four tools
- No approval queue infrastructure to build, monitor, or maintain
- Company skills inherit all the durability properties of source-controlled code: review, history, reproducibility, branch-based workflow
- The first two Company skills (`bopa.md`, `memory.md`) already exist — implementation has a real starting point
- User skills give individuals the tinker-friendly path without polluting org-wide knowledge

**Negative:**

- A regular advisor cannot directly contribute to Company skills — they must write a PR or ask an admin. For organisations where bottom-up procedure capture is important, this is friction
- Company skills can't be edited from the chat surface at all. Even an admin in the chatbot UI sees them as read-only
- We diverge from RM-Memory's scope model for skills; some users may find the inconsistency surprising (memory has 4 scopes; skills have 2)
- The "shadow company skill with a user-named one" pattern (§4) is rarely needed but introduces a small mental tax when it does happen

## Related ADRs

- **ADR-0013** — MCP-first capability strategy. This ADR is the implementation of §1's `rm-skills` reference. Skills diverge from §2's four-scope model deliberately
- **ADR-0014** — RM-Memory engine. The approval workflow built there is *not* reused for skills (§"What's intentionally absent")
- **ADR-0012** — Frontend strategy. Anthropic Pipe deferral is what makes catalog-injection-via-filter the right delivery mechanism today
- **ADR-0011** — Service-pattern AI surfaces. When Geoportaal's custom UI surfaces skills (e.g. "available BOPA skills" panel), it pulls from `list_skills` — same tool, both User and Company sources flow naturally

## Follow-up work

- **rm-skills authoring guide** for the model — when does a conversation become a User skill, how to populate steps/examples/parameters_shape. Likely added as a section to `memory.md` (now a Company skill) or as a sibling Company skill `skills.md`
- **Migration 007 + company-skill loader + tool implementation** — sequenced as one cycle each
- **Move existing skills into company/** — small but visible refactor; should land alongside or just before the company-skill loader
- **MCP-Servers ADR-0002 cross-reference** — note that skills now live in the same memory schema (separate table), with the simplified User-or-Company tier distinct from memory's four scopes
