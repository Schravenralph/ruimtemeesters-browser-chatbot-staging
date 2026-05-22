# ADR-0016: Persona-skill bindings for the Browser-Chatbot

**Date:** 2026-05-11 (refreshed 2026-05-20)
**Status:** Accepted
**Adopts:** Platform ADR-0008 (chat-skills as front door), Platform ADR-0011 (3-persona canon)
**Builds on:** ADR-0015 (rm-skills: User + Company), Platform ADR-0009 (thema-repo topology), Platform ADR-0010 (skills-as-processes)
**Related:** Platform ADR-0002 (Databank as sole intake), per-persona tool curation (now in scripts/personas.yaml per ADR-0018).

## TL;DR

The Browser-Chatbot ships **three persona models** (one per canon entry) and **nine Company skills** as of 2026-05-20 (refresh; was seven on 2026-05-11). Each skill is a markdown procedure with frontmatter in `Ruimtemeesters-Skills/skills/<name>/SKILL.md` per ADR-0015. Skills are persona-agnostic at the skill layer; persona routing happens via each SKILL.md's `personas:` frontmatter, or — for thema-driven skills — via the Scanmethode manifest (per ADR-0017).

## Decision

| #   | Decision                                                                   | Detail                                                                                                                                                                                                                                                                                     |
| --- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Three persona models, slugs match canon**                                | `RO-Assistent`, `Juridisch-Assistent`, `Commercieel-Assistent` (matching the LiteLLM routing key + OWUI Model row id + system-prompt persona name set in compose/seed via #82). Persona seeding consolidated into `scripts/personas.yaml` per ADR-0018.                                    |
| 2   | **Skill catalog committed to direction (table below)**                     | Nine skills shipped (BOPA, Beleidsscan, Legal References, plus three Commercieel skills and two meta skills), five planned. Each has a designated persona-of-record but is consumable by other personas when relevant.                                                                     |
| 3   | **Skill markdown lives in `Ruimtemeesters-Skills/skills/<name>/SKILL.md`** | Per ADR-0015. Each skill is a directory with `SKILL.md` plus optional support files; frontmatter declares `personas`, `requires_tools`, `mandatory` (default false), and optional `requires_themas` per ADR-0017.                                                                          |
| 4   | **Per-persona tool curation is the boundary mechanism**                    | Per-persona MCP tool curation is now declared in `scripts/personas.yaml` (`personas[].tool_ids`) per ADR-0018. A persona's available MCP tools constrain what its skills can call. New skills declare required MCP tools in `requires_tools`; the persona's `tool_ids` must include those. |
| 5   | **Skill→thema-repo routing uses the manifest**                             | Per Platform ADR-0010 §4, skills resolve a thema slug to a local thema-repo path via `00-Scanmethode/themas.yaml`. The exact resolution mechanism is in ADR-0017 (shipped as `packages/memory/src/tools/resolveThema.ts`).                                                                 |
| 6   | **No new persona without a Platform ADR**                                  | Per Platform ADR-0011 §5.                                                                                                                                                                                                                                                                  |

### What this ADR commits us to today

- New Company skill markdown lands in `MCP-Servers/packages/memory/skills/company/` and the skill is added to the catalog table in §"Skill catalog".
- New persona surfaces (model picker, slash command bindings, profile views) use exactly the three canon slugs.
- Per-persona tool curation gates skill capability; a skill cannot rely on a tool not in its persona's curation.

### What this ADR does not commit us to

- A build timeline for the six planned skills — that lives in a follow-up GH issue (referenced in §"Open items").
- The internal design of each planned skill (phase structure, prompts, nudging rules) — those are spec-territory.
- Reorganisation of the existing BOPA skill — refinement is tracked separately (see §"Open items").
- A position on User skills (DB-stored, personal) — those are user-owned per ADR-0015 and outside this catalog.

## Skill catalog

State as of 2026-05-20. Authoritative source: `Ruimtemeesters-Skills/skills/<name>/SKILL.md` frontmatter — this table summarises it.

| Skill                          | Status                | Persona-of-record     | Cross-persona use                              | Primary corpus consumed                                                     |
| ------------------------------ | --------------------- | --------------------- | ---------------------------------------------- | --------------------------------------------------------------------------- |
| **bopa**                       | Shipped               | ro-assistent          | juridisch-assistent (toetsing onderdelen)      | All 18 thema's — Phase 3 (Beleid) + Phase 4 (Omgevingsaspecten)             |
| **beleidsscan**                | Shipped               | ro-assistent          | juridisch-assistent (Omgevingsplan thema)      | 1 of 18 thema's per invocation; cross-references between related thema's    |
| **legal-references**           | Shipped (mandatory)   | juridisch-assistent   | —                                              | Omgevingswet / Bbl / Bal / gemeentelijke regelgeving — citation conventions |
| **parkeerbalans-onderbouwing** | Shipped (placeholder) | ro-assistent          | juridisch-assistent (onderbouwing)             | BOPA Phase 5 onderbouwing fragment — parking-balance impact                 |
| **acquisitie-prospect**        | Shipped               | commercieel-assistent | —                                              | `@rm-mcp/riens` × `@rm-mcp/opdrachten` × `@rm-mcp/sales-predictor`          |
| **gemeente-snapshot**          | Shipped               | commercieel-assistent | —                                              | `@rm-mcp/riens` + `@rm-mcp/opdrachten` + `@rm-mcp/memory`                   |
| **opdrachten-scan**            | Shipped               | commercieel-assistent | —                                              | `@rm-mcp/opdrachten` daily-inbox triage with memory-driven prioritisation   |
| **rm-memory-authoring** (meta) | Shipped               | all                   | all                                            | RM-Memory four-scope save/recall guidance per ADR-0014                      |
| **skill-authoring** (meta)     | Shipped               | all                   | all                                            | When a conversation becomes a User skill; `save_skill` shape per ADR-0015   |
| **locatiescan**                | Planned               | ro-assistent          | —                                              | Cross-thema light-touch; per-location snapshot                              |
| **mer-plichttoets**            | Planned               | ro-assistent          | juridisch-assistent (formal procedure aspects) | Multi-thema; legal-procedure-driven                                         |
| **participatietraject**        | Planned               | ro-assistent          | —                                              | `Ruimtemeesters-Scan-Participatie` primarily                                |
| **onderbouwing-schrijver**     | Planned               | ro-assistent          | juridisch-assistent (omgevingsplan wijziging)  | All 18 (writes from scan outputs)                                           |
| **visie-kader-analyse**        | Planned               | ro-assistent          | —                                              | All 18 (analyses incoming visies, maps to thema's)                          |

### Persona ownership consequence

- **RO Assistent** owns `bopa`, `beleidsscan`, `parkeerbalans-onderbouwing` today; will own all five planned skills (`locatiescan`, `mer-plichttoets`, `participatietraject`, `onderbouwing-schrijver`, `visie-kader-analyse`) on completion. Primary skill consumer.
- **Juridisch Assistent** owns `legal-references` (mandatory) and consumes `beleidsscan` when targeting the Omgevingsplan thema, `bopa` for legal-toetsing aspects, and (when shipped) `mer-plichttoets` + `onderbouwing-schrijver`.
- **Commercieel Assistent** owns three skills shipped 2026-04 → 2026-05: `acquisitie-prospect`, `gemeente-snapshot`, `opdrachten-scan`. The original ADR-0016 framing ("candidate, not committed") is superseded — the Commercieel side is now a first-class persona surface with its own skill set.
- **Meta skills** (`rm-memory-authoring`, `skill-authoring`) are persona-agnostic — every persona invokes them when authoring memories or skills.

## Per-persona tool curation (declarative)

Per-persona tool curation is declared in `scripts/personas.yaml` (`personas[].tool_ids`) per ADR-0018. Boundary rule: **a skill's `requires_tools` frontmatter (per ADR-0015 §2) must be a subset of the invoking persona's curated tools**.

Concrete bindings as of 2026-05-20 (authoritative source: `scripts/personas.yaml`):

| Persona               | Curated MCP tools                                                                      |
| --------------------- | -------------------------------------------------------------------------------------- |
| ro-assistent          | rm-databank, rm-geoportaal, rm-tsa, rm-dashboarding, rm-aggregator, rm-memory          |
| juridisch-assistent   | rm-databank, rm-aggregator, rm-memory                                                  |
| commercieel-assistent | rm-opdrachten, rm-riens, rm-sales-predictor, rm-dashboarding, rm-aggregator, rm-memory |

## Consequences

| Area                            | Consequence                                                                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/personas.yaml`         | Owns persona tool curation (ADR-0018). Three persona entries matching canon.                                                               |
| `Ruimtemeesters-Skills/skills/` | Receives new skill directories as planned skills are built. Frontmatter declares `personas`, `requires_tools`, optional `requires_themas`. |
| `product-docs/25-assistants/`   | Stale per `project_persona_canon` memory; cleanup deferred — content is non-canonical, ignore.                                             |
| Per-persona tool curation       | New skills add their required MCP tools to the relevant persona's `tool_ids` in `personas.yaml`. PR review checks the subset-rule.         |
| Reviewers                       | New check: any skill PR declares `personas` + `requires_tools`; the persona's `tool_ids` in `personas.yaml` must contain those tools.      |

## Revision history

- **2026-05-20** — Refresh: status Proposed → Accepted. Catalog re-baselined against `Ruimtemeesters-Skills/skills/` on disk (9 shipped, 5 planned). Three Commercieel skills (`acquisitie-prospect`, `gemeente-snapshot`, `opdrachten-scan`) reclassified from "candidate, not committed" → shipped. Two meta skills (`rm-memory-authoring`, `skill-authoring`) added. `legal-references` and `parkeerbalans-onderbouwing` added. Skill location updated from `MCP-Servers/packages/memory/skills/company/` to `Ruimtemeesters-Skills/skills/` (the latter is the live home; the former is a legacy reference). Per-persona tool curation re-pointed at `scripts/personas.yaml` (ADR-0018).
- **2026-05-11** — Original draft (Proposed status, 1 shipped + 6 planned catalog, `feat/per-persona-tool-curation` branch in flight).

## Open items (not blocked by this ADR)

- Build the five remaining planned skills (suggested order, smallest-first: `locatiescan`, `onderbouwing-schrijver`, `mer-plichttoets`, `participatietraject`, `visie-kader-analyse`).
- BOPA skill refinement (Phase 5 onderbouwing thinness, Phase 4 omgevingsaspecten coverage).
- `parkeerbalans-onderbouwing` is `status: placeholder` — fill in the actual content.
