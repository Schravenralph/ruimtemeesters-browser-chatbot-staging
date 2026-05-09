---
forge_cycle: 3
date: 2026-04-30
size: small
---

# Forge Spec: `/bopa-status` slash prompt — list active BOPA sessions

## What

Add a 12th slash prompt to `register_assistants.py`: `/bopa-status` that
instructs the general agent to call `list_bopa_sessions({})` on the
rm-memory MCP server and present a human-readable summary of the user's
active BOPA evaluations — phase progress, next logical step, blockers.

## Why

Cycles 1+2 wired up the BOPA workflow on `chat.datameesters.nl`, but
there's no easy "where was I?" entry point. An advisor returning after
a few days has to remember session IDs or project IDs to pick up an
evaluation. With BOPA state in `rm-memory`, the data is there — what's
missing is a one-touch slash command that surfaces it.

This is a discovery / continuity feature, not a workflow phase.
Specifically NOT a Phase 4–6 prompt (those are deferred behind missing
MCP tools).

## Success criteria

1. `python3 rm-tools/register_assistants.py --dry-run` reports
   `5/5 + 12/12` (was 11).
2. The new prompt's content names `list_bopa_sessions`, `dependencies_met`,
   and asks for phase progress per session.
3. `python3 -m py_compile` passes.

## Approach

One Edit on `register_assistants.py` PROMPTS list — append the new
dict immediately above the existing BOPA phase prompts so all 4 BOPA
commands cluster in the registrar. Defensive content: if the empty
filter `{}` isn't accepted by the MCP server, the prompt instructs the
agent to fall back to asking the user for `gemeente_code` / `project_id`.

## Not doing

- Inline rendering of session state in OpenWebUI's chat header
  (UI-side; that's the §6 follow-up "OpenWebUI inlet filter to
  auto-inject active BOPA session summary").
- Any backend or memory-server change.
- A "delete session" or "archive session" prompt — destructive
  operations need explicit per-session confirmation, not a slash.
