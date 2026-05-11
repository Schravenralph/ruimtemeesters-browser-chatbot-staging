# ADR-0016: Persona-skill bindings for the Browser-Chatbot

**Date:** 2026-05-11
**Status:** Proposed
**Adopts:** Platform ADR-0008 (chat-skills as front door), Platform ADR-0011 (3-persona canon)
**Builds on:** ADR-0015 (rm-skills: User + Company), Platform ADR-0009 (thema-repo topology), Platform ADR-0010 (skills-as-processes)
**Related:** Platform ADR-0002 (Databank as sole intake), `feat/per-persona-tool-curation` branch (already in flight).

## TL;DR

The Browser-Chatbot ships **three persona models** (one per canon entry) and **seven Company skills** (one committed, six planned). Each skill is a markdown procedure in `Ruimtemeesters-MCP-Servers/packages/memory/skills/company/` per ADR-0015. Skills are persona-agnostic at the skill layer; persona routing happens via the thema-repo's `AGENTS.md` declaration (per Platform ADR-0009 §6) or the skill's own persona-of-record when no thema is involved.

## Decision

| #   | Decision                                                                  | Detail                                                                                                                                                                                                                                                                             |
| --- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Three persona models, slugs match canon**                               | `rm-ro-adviseur`, `rm-juridisch-adviseur`, `rm-commercieel-adviseur`. Existing model entries that don't match are stale (see Platform ADR-0011 cleanup list) and get removed in a follow-up PR.                                                                                    |
| 2   | **Skill catalog committed to direction (table below)**                    | One skill (`bopa`) is shipped; six are planned. Each has a designated persona-of-record but is consumable by other personas when relevant.                                                                                                                                         |
| 3   | **Skill markdown lives in `MCP-Servers/packages/memory/skills/company/`** | Per ADR-0015. Each skill is a single file: `bopa.md`, `beleidsscan.md`, `locatiescan.md`, `mer-plichttoets.md`, `participatietraject.md`, `onderbouwing-schrijver.md`, `visie-kader-analyse.md`.                                                                                   |
| 4   | **Per-persona tool curation is the boundary mechanism**                   | The Browser-Chatbot already implements per-persona MCP tool curation (`feat/per-persona-tool-curation`). A persona's available MCP tools constrain what its skills can call. New skills declare required MCP tools in their frontmatter; persona tool-curation must include those. |
| 5   | **Skill→thema-repo routing uses the manifest**                            | Per Platform ADR-0010 §4, skills resolve a thema slug to a local thema-repo path via `00-Scanmethode/themas.yaml`. The exact resolution mechanism is in ADR-0017 (downstream).                                                                                                     |
| 6   | **No new persona without a Platform ADR**                                 | Per Platform ADR-0011 §5.                                                                                                                                                                                                                                                          |

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

| Skill                      | Status                  | Persona-of-record | Cross-persona use                                             | Primary thema-repos consumed                                                         |
| -------------------------- | ----------------------- | ----------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **bopa**                   | Shipped                 | ro-adviseur       | juridisch-adviseur (toetsing onderdelen)                      | All 18 — BOPA Phase 3 (Beleid) and Phase 4 (Omgevingsaspecten) scan multiple thema's |
| **beleidsscan**            | Planned (active design) | ro-adviseur       | juridisch-adviseur (for Omgevingsplan thema)                  | 1 of 18 per invocation; cross-references for closely related thema's (e.g. #1 ↔ #18) |
| **locatiescan**            | Planned                 | ro-adviseur       | —                                                             | Cross-thema light-touch; per-location snapshot                                       |
| **mer-plichttoets**        | Planned                 | ro-adviseur       | juridisch-adviseur (formal procedure aspects)                 | Multi-thema; legal-procedure-driven                                                  |
| **participatietraject**    | Planned                 | ro-adviseur       | —                                                             | `Ruimtemeesters-Scan-Participatie` primarily                                         |
| **onderbouwing-schrijver** | Planned                 | ro-adviseur       | juridisch-adviseur (for omgevingsplan wijziging onderbouwing) | All 18 (writes from scan outputs)                                                    |
| **visie-kader-analyse**    | Planned                 | ro-adviseur       | —                                                             | All 18 (analyses incoming visies, maps to thema's)                                   |

### Persona ownership consequence

- **RO adviseur** invokes all seven skills; primary owner.
- **Juridisch adviseur** invokes `beleidsscan` when targeting Omgevingsplan (thema #15 per P-0009), `mer-plichttoets` when the procedure-formality is the focus, `onderbouwing-schrijver` when writing a juridische onderbouwing, and `bopa` for legal-toetsing aspects.
- **Commercieel adviseur** currently invokes none — consumes scan _outputs_ via `Document-Generator` or direct file reads, but does not drive scans. A future commercial-side skill (e.g. `tender-go-no-go`) is a candidate; tracked as out-of-scope here.

## Per-persona tool curation (already implemented)

The `feat/per-persona-tool-curation` branch curates MCP tools per persona so a persona's chat surface only exposes tools relevant to its role. This ADR codifies that pattern as the boundary mechanism: **a skill's `requires_tools` frontmatter (per ADR-0015 §2) must be a subset of the invoking persona's curated tools**.

Concrete bindings (subject to refinement as skills are built):

| Persona              | Curated MCP tools (high level)                                                                             |
| -------------------- | ---------------------------------------------------------------------------------------------------------- |
| ro-adviseur          | rm-geoportaal (all), rm-databank (search/tagging), rm-memory, rm-aggregator, rm-document-generator         |
| juridisch-adviseur   | rm-databank (search/tagging), rm-wetten, rm-nieuwsbrief (jurisprudentie), rm-memory, rm-document-generator |
| commercieel-adviseur | rm-riens, rm-opdrachten-scanner, rm-sales-predictor, rm-memory, rm-crm, rm-mailchimp                       |

## Consequences

| Area                                          | Consequence                                                                                                                                     |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `rm-tools/register_assistants.py`             | Three persona entries; stale entries removed in follow-up PR.                                                                                   |
| `MCP-Servers/packages/memory/skills/company/` | Receives six new skill markdown files as planned skills are built.                                                                              |
| `product-docs/25-assistants/`                 | Replaced with three persona docs matching canon (separate PR, per Platform ADR-0011 cleanup).                                                   |
| Per-persona tool curation                     | New skills add their required MCP tools to the relevant persona's curation. PR review checks the subset-rule.                                   |
| Reviewers                                     | New check: any skill markdown PR declares persona-of-record + required MCP tools; the curation lists must contain those tools for that persona. |

## Open items (not blocked by this ADR)

- Follow-up GH issue tracks design and build priority for the six planned skills (Beleidsscan first, then Locatiescan, m.e.r.-plichttoets, Participatietraject, Onderbouwing-schrijver, Visie/kader-analyse). To be opened after this ADR lands.
- BOPA skill refinement (Phase 5 onderbouwing thinness, Phase 4 omgevingsaspecten coverage) — tracked in the same follow-up issue.
- A future `tender-go-no-go` or similar commercial-side skill for Commercieel adviseur — candidate, not committed.
- Cleanup PRs: stale persona model entries, stale `product-docs/25-assistants/` docs.
