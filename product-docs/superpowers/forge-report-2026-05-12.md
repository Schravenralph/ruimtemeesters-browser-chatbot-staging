# Forge Report — 2026-05-12

**Wall clock:** 2.3h
**Cycles completed:** 4
**Features shipped:** 4 merged across 3 repos + 17 new repos minted

## Shipped Features

| # | Cycle | Repo | PR / Action | Status | Size |
|---|---|---|---|---|---|
| 1 | 25-assistants canon cleanup | Browser-Chatbot | [#89](https://github.com/Schravenralph/Ruimtemeesters-Browser-Chatbot/pull/89) | merged | S |
| 2a | Volkshuisvesting GitHub rename + 61-commit push | Scan-Volkshuisvesting | direct rename via gh + push | done | — |
| 2b | Scanmethode cross-repo reference update | Scanmethode | [#1](https://github.com/Schravenralph/Ruimtemeesters-Scanmethode/pull/1) | merged | XS |
| 2c | Volkshuisvesting self-references | Scan-Volkshuisvesting | [#8](https://github.com/Schravenralph/Ruimtemeesters-Scan-Volkshuisvesting/pull/8) | merged | XS |
| 2d | Orphan Thematische-Beleidsscans wrapper removed; Scanmethode clone promoted to top level | local FS | — | done | — |
| 3 | `resolveThema` + `resolve_thema` + `list_themas` (MCP tools) | MCP-Servers | [#83](https://github.com/Schravenralph/Ruimtemeesters-MCP-Servers/pull/83) | merged | M |
| 4 | Mint 17 Scan-* repos from themas.yaml @ depth B | GitHub | bootstrap.py + gh repo create | done | M |

## Impact

### New capabilities

- **Persona-canon coherent end-to-end** — `product-docs/25-assistants/` no longer carries the 5-persona pre-canon layout; it matches LiteLLM, OWUI seed, and ADRs 0011/0016/0017.
- **Manifest-driven thema resolution shipped** — skills (Beleidsscan today, planned skills tomorrow) can call `resolve_thema(slug)` instead of inlining YAML parsing in LLM reasoning, per ADR-0017 §4.
- **18 thema-corpora exist on GitHub** — every entry in `themas.yaml` now resolves to a real repo. The Beleidsscan skill can be exercised against any thema without "repo not cloned" hard-stops (once the corpora are also mounted at `$RM_SCANS_ROOT`).

### Tooling expansion

- `@rm-mcp/memory` now exports a `ResolveThemaError` typed-error pattern that future filesystem-coupled tools can mirror (typed `code` per failure mode + structured `details`).
- Registry / integration tests are no longer stale; they snapshot all 19 tools and were aligned to the actual catalog. CI on `MCP-Servers` main was red on the registry test prior to this session — now green.

## Unfinished / Next Session

| Pri | Item | Why | Est. size |
|---|---|---|---|
| 1 | **Wire `beleidsscan.md` to call `resolve_thema` by name** | The MCP tool exists but the skill still documents the algorithm inline as pseudocode. One docs edit; ships the tool. | XS |
| 2 | **Amend ADR-0017 §1 default path** | The stale default `~/Projects/Ruimtemeesters-Thematische-Beleidsscans/` no longer exists; the new local-clone topology mixes Scan-* repos directly under `~/Projects/`. ADR amendment + a `setup-scans-workspace.sh` that creates the symlinks the resolver expects. | S |
| 3 | **The five other planned skills** (Locatiescan, m.e.r.-plichttoets, Participatietraject, Onderbouwing-schrijver, Visie/kader-analyse) | Tracked in MCP-Servers #85. Each is its own design cycle. | L (per skill) |
| 4 | **Promote canonical methodology text from Scan-Volkshuisvesting → Scanmethode** | Scanmethode `README.md` + `AGENTS.md` already flag this. Move generic content out of the Volkshuisvesting repo and into the meta-repo. | S |
| 5 | **Seed `kennis/geconsolideerd.md` per thema** (where canon exists) | The 17 new repos all carry empty placeholders. Where we already know the canon (Volkshuisvesting, Omgevingsplan), copy it across. | M |

## Observations

- **Discovery before action paid off.** The cycle-2 scout surfaced three pieces of unexpected state (Evenementenbeleid never existed on GitHub, Volkshuisvesting had 61 unpushed commits, the Thematische-Beleidsscans local wrapper was orphan). Asking before acting prevented destructive shortcuts.
- **Registry test was a landmine.** A hardcoded list of tool names that PR #82 didn't update meant CI was quietly red. New tools require a registry-test edit — this is brittle; future "add a tool" cycles should consider a snapshot file or auto-derivation.
- **Bootstrap script over per-repo manual** was a clear win. 17 `gh repo create` invocations with consistent content via one Python script instead of 17 hand-edits.
- **The user-confirmed pauses (cycle 2 decisions, cycle 4 depth) saved scope creep.** The "should I create 17 repos at depth A/B/C?" gate prevented either gold-plating (cloning Volkshuisvesting content into unrelated themas) or under-shipping (empty repos that fail the schema-conformance check).
