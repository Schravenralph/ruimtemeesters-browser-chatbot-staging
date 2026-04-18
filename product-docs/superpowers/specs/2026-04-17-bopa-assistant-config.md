# Spec — BOPA workflow as a skill on the general OpenWebUI agent

**Date:** 2026-04-17 (revised: single-agent correction)
**Status:** Approved (proactive-brainstorm cycle, single item)
**Repo:** `Ruimtemeesters-Browser-Chatbot`
**Depends on:** Ruimtemeesters-MCP-Servers PR #4 (`@rm-mcp/memory`) + PR #5 (gateway route) — merged.

## 1. Goal

Unlock the BOPA workflow for advisors using `chat.datameesters.nl` **without introducing a new specialist assistant**. Per the project's single-agent policy (feedback memory `feedback_single_agent_no_multi_assistant.md`), the direction is **one general agent with skills + slash prompts**, like Claude Code — not a fleet of role-specific assistants.

So: wire the general assistant (`rm-assistent`) to the now-merged `@rm-mcp/memory` and ship the BOPA workflow as a skill file + 3 slash prompts. The advisor invokes the workflow via `/bopa-haalbaarheid` (or similar) on the general assistant.

End-to-end unlock: an advisor picks **Ruimtemeesters Assistent**, types `/bopa-haalbaarheid` with an address, and the agent uses memory for session state + databank for policy docs + geoportaal for spatial checks.

## 2. Non-goals (deferred)

- Registering the MCP external-tool-servers programmatically (OpenWebUI's admin API is undocumented; admin UI setup documented instead)
- Phase 5/6 BOPA tools — blocked on follow-up PR to memory package
- **Consolidating the 5 pre-existing specialist assistants** (beleidsadviseur, demografie-analist, ruimtelijk-adviseur, sales-adviseur, rm-assistent) — separate follow-up PR per the single-agent policy

## 3. Changes

### A. `rm-tools/register_assistants.py`

- `rm-assistent` (the general assistant) — add `"server:mcp:rm-memory"` to its `toolIds` so the general surface can read/write BOPA session state. Update its system prompt to mention memory alongside the other tools.
- **NO new specialist assistant.** BOPA workflow is a skill invoked via slash prompts, not a role.

### B. `rm-tools/register_assistants.py` — `PROMPTS` array

Add 3 BOPA slash prompts: `/bopa-haalbaarheid`, `/bopa-strijdigheid`, `/bopa-beleid`. Each wraps a phase-specific tool sequence.

### C. `.claude/skills/bopa/SKILL.md`

Copy of the canonical BOPA skill from `Ruimtemeesters-MCP-Servers/packages/memory/skills/bopa.md`. Lets Claude Code users run the same flow.

### D. `rm-tools/ADMIN_SETUP.md` (NEW)

One-time admin-UI checklist for registering the 9 MCP external tool servers in OpenWebUI. Exact server-ID strings (must match `meta.toolIds`). Sanity-check curl for `rm-memory`.

### E. `--dry-run` flag on `register_assistants.py`

Token no longer required when `--dry-run`. Prints payload summaries for CI inspection.

## 4. Success criteria

| Criterion                                                                                    | Threshold                 | How measured                                   |
| -------------------------------------------------------------------------------------------- | ------------------------- | ---------------------------------------------- |
| General assistant `rm-assistent` includes `rm-memory` in toolIds                             | yes                       | diff + API check                               |
| 3 BOPA slash prompts registered (`/bopa-haalbaarheid`, `/bopa-strijdigheid`, `/bopa-beleid`) | yes                       | API: `GET /api/v1/prompts`                     |
| **NO new specialist assistant introduced**                                                   | confirmed                 | registrar shows 5 assistants, same as baseline |
| `.claude/skills/bopa/SKILL.md` exists and matches canonical source                           | yes                       | diff against `packages/memory/skills/bopa.md`  |
| `ADMIN_SETUP.md` lists 9 MCP servers                                                         | yes                       | file exists                                    |
| Registrar syntax check                                                                       | pass                      | `python3 -m py_compile`                        |
| Registrar dry-run                                                                            | 5 assistants + 11 prompts | `python3 register_assistants.py --dry-run`     |

## 5. Validation

1. **Lint:** `python3 -m py_compile rm-tools/register_assistants.py`
2. **Dry-run:** `python3 rm-tools/register_assistants.py --dry-run` → 5/5 + 11/11 clean
3. **Staging integration** (post-deploy):
   - Admin runs `register_assistants.py`
   - Admin registers the 9 tool servers per `ADMIN_SETUP.md`
   - Smoke: pick **Ruimtemeesters Assistent**, type `/bopa-haalbaarheid` with a real address, expect a `create_bopa_session` tool call
4. **SQL check:** `SELECT count(*) FROM memory.bopa_sessions WHERE api_key_name LIKE 'gateway:%';` ≥ 1

## 6. Follow-ups

1. **Consolidate the 5 pre-existing specialist assistants** into `rm-assistent` + per-workflow skills + slash prompts. Separate PR per the single-agent policy.
2. `/bopa-omgevingsaspecten`, `/bopa-onderbouwing`, `/bopa-toetsing` slash prompts — ship when matching MCP tools land.
3. Skill-sync mechanism between `packages/memory/skills/bopa.md` and `.claude/skills/bopa/SKILL.md` (currently manual copy).
4. OpenWebUI inlet filter to auto-inject active BOPA session summary.
