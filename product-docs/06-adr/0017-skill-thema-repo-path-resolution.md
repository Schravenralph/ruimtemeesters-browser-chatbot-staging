# ADR-0017: Skill→thema-repo path resolution via manifest and env var

**Date:** 2026-05-11 (refreshed 2026-05-20)
**Status:** Accepted
**Adopts:** Platform ADR-0009 (thema-repo topology + local clone convention), Platform ADR-0010 (skills-as-processes / one-way dependency rule)
**Builds on:** ADR-0015 (rm-skills), ADR-0016 (persona-skill bindings)
**Related:** Platform ADR-0008 (chat-skills as front door).
**Implementation:** `Ruimtemeesters-MCP-Servers/packages/memory/src/tools/resolveThema.ts` (+ `listThemas.ts`, `registry.ts`, with full unit + integration test coverage).

## TL;DR

Skills in `Ruimtemeesters-Skills/skills/<name>/SKILL.md` resolve a thema slug (e.g. `volkshuisvesting`) to a local thema-repo path by reading **`themas.yaml` in the Scanmethode meta-folder**, located via the **`RM_SCANS_ROOT`** environment variable. The convention is uniform across dev (local Projects folder) and prod (mounted volume). Skills MUST NOT hard-code paths; resolution always goes through `resolveThema()` on the rm-memory MCP.

## Decision

| #   | Decision                                                                | Detail                                                                                                                                                                                                                                   |
| --- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **`RM_SCANS_ROOT` env var points to the Scan-repos parent directory**   | Default in dev: `~/Projects/Ruimtemeesters-Beleidsscans/`. In Docker: a mounted volume path, e.g. `/srv/rm-scans/`. The env var is the only configuration point.                                                                         |
| 2   | **The manifest lives at `${RM_SCANS_ROOT}/00-Scanmethode/themas.yaml`** | Single source of truth for slug → repo → persona → folder mapping. Resolved once per skill invocation.                                                                                                                                   |
| 3   | **Manifest schema is typed and versioned**                              | YAML with a `version` field. Schema documented in Scanmethode README; future changes are backwards-compatible or require a `version` bump.                                                                                               |
| 4   | **Resolution helper lives on the rm-memory MCP**                        | Shipped at `Ruimtemeesters-MCP-Servers/packages/memory/src/tools/resolveThema.ts`. Company skills call the MCP tool `resolveThema(slug) → { repoName, persona, localPath, githubUrl }`. No skill markdown re-implements resolution.      |
| 5   | **Missing manifest or missing thema-repo is a typed error**             | The resolver returns `{ ok: false, code: '...' }` with a typed `code` when the manifest is missing, the slug is unknown, or the corpus isn't cloned. Skills surface that message to the user and refuse to scan — no silent degradation. |
| 6   | **Skill markdown declares thema dependencies in frontmatter**           | A skill that needs thema-corpus content declares `requires_themas: ["{slug}"] \| "any"` so the runtime can pre-check availability before the conversation starts.                                                                        |

### Manifest shape (informative — exact schema in Scanmethode)

```yaml
version: 1
themas:
  - slug: volkshuisvesting
    number: 1
    title: 'Wonen / Volkshuisvesting'
    github_repo: Ruimtemeesters-Scan-Volkshuisvesting
    local_folder: 01-Scan-Volkshuisvesting
    persona: ro-assistent
    cross_refs: [arbeidsmigranten-huisvesting]
  - slug: omgevingsplan
    number: 15
    title: 'Omgevingsplan'
    github_repo: Ruimtemeesters-Scan-Omgevingsplan
    local_folder: 15-Scan-Omgevingsplan
    persona: juridisch-assistent
    cross_refs: []
  # ... 16 more
```

### Resolution algorithm

```
resolveThema(slug):
  1. Read $RM_SCANS_ROOT (error if unset)
  2. Load $RM_SCANS_ROOT/00-Scanmethode/themas.yaml (error if missing)
  3. Find entry with matching slug (error if missing)
  4. Compute localPath = $RM_SCANS_ROOT/<local_folder>
  5. Verify localPath exists (error if missing — corpus not cloned)
  6. Return { repoName, persona, localPath, githubUrl, cross_refs }
```

Step 5's check is per-invocation; in Docker prod this catches "thema-repo not synced to volume yet" before the chat invests turns in a doomed scan.

### What this ADR commits us to today

- The Beleidsscan skill (and any future skill that consumes thema-corpus content) calls `resolveThema` rather than reading paths directly.
- Frontmatter for thema-consuming skills declares `requires_themas`.
- Local dev uses `RM_SCANS_ROOT=~/Projects/Ruimtemeesters-Beleidsscans/`.
- Container builds for MCP-Servers / chatbot accept `RM_SCANS_ROOT` as an env var and document its expected mount target.

### What this ADR does not commit us to

- A specific production sync mechanism (git-sync sidecar? rsync cronjob? object-storage mirror? committed-as-image-layer?) — deployment detail, separate decision.
- A specific TypeScript framework choice for the resolver — implementation detail.
- A position on whether GitHub API fallback is allowed for missing local content — currently NO (per decision #5), revisit if mount reliability proves a problem.
- A position on caching strategy (read-once-per-process? per-invocation? watch-file-changes?) — implementation detail.

## Consequences

| Area                           | Consequence                                                                                                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Skill markdown                 | Each thema-consuming skill declares `requires_themas` in frontmatter. Skills never read absolute paths.                                                          |
| MCP-Servers                    | New resolver module in `packages/memory/`. Unit-tested with a fixture manifest.                                                                                  |
| Scanmethode meta-repo          | Maintains `themas.yaml` as the canonical manifest. Updates to it are version-controlled. Schema doc in the repo's README.                                        |
| Browser-Chatbot Docker compose | Adds `RM_SCANS_ROOT` env var with a sensible default mount path; documents the mount in compose comments.                                                        |
| Dev environment                | Developers clone the 18 + Scanmethode into `~/Projects/Ruimtemeesters-Beleidsscans/` and set `RM_SCANS_ROOT` (or use the default).                               |
| Prod deployment                | The corpus needs to be available at `$RM_SCANS_ROOT` inside the container. Mechanism deferred — but the contract (env var + manifest + folder layout) is locked. |
| Reviewers                      | New check: thema-consuming skill PRs declare `requires_themas` and call `resolveThema`; raw filesystem reads against thema paths are flagged.                    |

## Revision history

- **2026-05-20** — Refresh: status Proposed → Accepted. Implementation reference added (`packages/memory/src/tools/resolveThema.ts` shipped with unit + integration tests). Default `RM_SCANS_ROOT` corrected from `~/Projects/Ruimtemeesters-Thematische-Beleidsscans/` to `~/Projects/Ruimtemeesters-Beleidsscans/` (matches the actual repo name on disk + `themas.yaml` location). Skill home updated from `MCP-Servers/packages/memory/skills/company/` to `Ruimtemeesters-Skills/skills/<name>/SKILL.md`. Decision #5 clarified to match the shipped typed-error contract.
- **2026-05-11** — Original draft (Proposed status).

## Open items (not blocked by this ADR)

- Production sync mechanism for thema-corpora into the deployed chatbot — design decision, separate ADR or operations doc.
- Whether `resolveThema` should support a GitHub-API fallback when local content is missing — explicitly NO today; revisit when needed.
- The exact JSON Schema for `themas.yaml` validation — lives in Scanmethode, populated when the manifest is first written.
- How updates to `themas.yaml` propagate to a running container (restart? SIGHUP? file-watch?) — implementation detail.
