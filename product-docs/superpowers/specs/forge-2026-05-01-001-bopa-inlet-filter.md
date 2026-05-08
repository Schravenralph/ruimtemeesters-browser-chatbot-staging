---
forge_cycle: 1
date: 2026-05-01
size: medium
---

# Forge Spec: BOPA active-session inlet filter

## What

A new OpenWebUI filter function (`bopa_session_context`) that runs on every
inlet to `rm-assistent`, looks up the user's most-recently-updated active
BOPA session via the rm-memory MCP, and appends a short summary block to
the system message before the LLM call. No tool call required from the
agent — the context is already there when the chat opens.

Concrete deliverables:

1. **Filter source**: `rm-tools/filters/bopa_session_context.py` — a
   self-contained Filter module (Valves + async `inlet`) following the
   plugin pattern that `backend/open_webui/utils/filter.py:55-125` loads.
2. **Registrar**: extend `rm-tools/register_assistants.py` with a
   `FILTERS = [...]` list and a `register_filter` function that POSTs the
   filter content to `/api/v1/functions/create` (or update). The filter is
   attached to `rm-assistent` via `meta.filterIds`.
3. **Tests**: `rm-tools/tests/test_bopa_inlet_filter.py` — pure-Python
   unit tests for the filter's session-selection logic and prompt-shaping,
   with the MCP HTTP call mocked. No integration test in this cycle.
4. **Documentation**: a one-page `product-docs/30-tools/bopa-inlet-filter.md`
   explaining what the filter does, when it injects, and how to disable
   per-user via `UserValves`.

## Why

Yesterday's cycles 1–3 (PRs #26, #27, #28) made the BOPA workflow
**discoverable**: starter cards on `rm-assistent`, three `/bopa-*` slash
prompts, and `/bopa-status` for continuity. The remaining gap is the
day-3 case: an advisor returns to `chat.datameesters.nl` after a few days,
opens a fresh chat with `rm-assistent`, and the model has zero context on
the BOPA project they were working on. Today they have to type
`/bopa-status` manually — a step that depends on remembering it exists.

This filter closes that loop. Yesterday's forge report ranked it as the #1
follow-up (`docs/superpowers/forge-report-2026-04-30.md` line 67), citing
spec `2026-04-17-bopa-assistant-config.md` §6 follow-up #4. It's
pre-validated, advisor-visible, and the only Phase-D-flavored work that
can ship in a single forge cycle.

## Success criteria

1. Opening a fresh chat with `rm-assistent` while having an
   `status='active'` BOPA session in `memory.bopa_sessions` injects a
   summary block into the system prompt visible in the chat completion
   request body (verifiable via OpenWebUI's request log or a curl trace
   against `/api/chat/completions`).
2. The summary contains: `session_id`, `project_key`, `gemeente_code`,
   `current_phase`, `completed_phases`, `dependencies_met`, and a one-line
   "next logical step" derived from `dependencies_met`.
3. When the user has zero active BOPA sessions, the filter is a no-op —
   no extra system content, no failed-RPC error surfaced to the user.
4. When the rm-memory MCP is unreachable (timeout, 5xx), the filter logs
   a warning and returns `body` unchanged. Chat must still work.
5. The filter only fires for `rm-assistent`. Switching to any other
   specialist (`rm-demografie-analist`, etc.) leaves the system prompt
   untouched.
6. Per-user opt-out: a `UserValves.enabled = False` in the user's filter
   settings disables injection for that user only (covers privacy concerns
   for users who don't want BOPA state pre-loaded).

## Approach

### Session selection

The rm-memory `list_bopa_sessions` tool (in
`Ruimtemeesters-MCP-Servers/packages/memory/src/tools/`) returns sessions
across all callers — BOPA sessions are project-scoped per spec
`2026-04-20-memory-scoping-model.md` §9 (verified in
`getBopaSession.ts:8-10`: "owner filter previously applied on reads has
been dropped"). The filter therefore:

1. Calls `list_bopa_sessions` (no input filter).
2. Client-side filters rows where `owner_user_id == __user__.id`.
3. Filters to `status == 'active'`.
4. Sorts by `updated_at` desc, picks index 0.

If multiple active sessions exist, only the most-recent is injected — the
summary includes the count so the advisor knows others exist and can
disambiguate via `/bopa-status`.

### MCP transport

Filter speaks JSON-RPC over HTTP POST to `http://rm-mcp-memory:3200/mcp`
(value comes from compose `TOOL_SERVER_CONNECTIONS`, hardcoded as a Valve
default with env-var fallback). Auth header:
`Authorization: Bearer ${MEMORY_GATEWAY_TOKEN}` — same as compose. Body:
`{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_bopa_sessions", "arguments": {}}}`.

Timeout: 800ms. Cache: in-memory `(user_id, ttl=30s)` dict on the filter
module — no per-request hammer when an advisor sends 3 messages in a row.

### Prompt shape

Appended to the system message via
`add_or_update_system_message(summary, messages, append=True)`
(`backend/open_webui/utils/misc.py:384`). Format:

```
---
ACTIEVE BOPA-SESSIE
Sessie: {session_id} ({project_key} — {gemeente_code})
Status: fase {current_phase}/6 actief, afgeronde fasen: {completed_phases}
Volgende fase: {next_phase} (klaar) | Geblokkeerd op: {blocked_on}
Tip: gebruik /bopa-status voor het volledige overzicht of /bopa-{volgende-fase} om door te gaan.
{N andere actieve sessies — gebruik /bopa-status om te schakelen.}  # only if N>0
```

The "next phase" is derived locally from `dependencies_met` (the same
logic that `getBopaSession.ts:115` exposes via
`computeDependenciesMet`) — this avoids a second RPC.

### Attachment to `rm-assistent`

Via `meta.filterIds = ['bopa_session_context']` in the rm-assistent
payload in `register_assistants.py`. Specialists are untouched. Yesterday's
v1 only — extending to the other 4 specialists is a follow-up cycle once
we have UX evidence the injection is helpful and not noisy.

### Failure modes

| Failure                      | Behavior                                 |
| ---------------------------- | ---------------------------------------- |
| MCP timeout (>800ms)         | Log warning, no injection, chat proceeds |
| MCP 5xx / connection refused | Log warning, no injection                |
| Empty user (e.g. anonymous)  | No injection                             |
| `__user__` missing           | No injection (defensive)                 |
| `UserValves.enabled = False` | No injection                             |
| No active sessions for user  | No injection                             |

## Not doing

- **No injection on the 4 specialist assistants.** v1 only on
  `rm-assistent`. Extending is one config line per specialist in a
  follow-up cycle once we observe the v1 UX.
- **No write path.** The filter never updates the BOPA session — it's
  read-only context priming.
- **No new MCP tools.** Phase 4–6 BOPA tools (`bopa_omgevingsaspecten`,
  `bopa_onderbouwing`, `bopa_toetsing`) remain blocked on
  `Ruimtemeesters-MCP-Servers/packages/memory/src/tools/` shipping them.
  This filter only consumes existing `list_bopa_sessions`.
- **No outlet filter.** Only inlet — appending to system prompt before
  LLM call. We don't post-process the model's response.
- **No multi-session merge.** Most-recent active wins. Showing all of
  them inline would balloon the system prompt; advisor uses
  `/bopa-status` for the full list.
- **No skill-sync work** between `packages/memory/skills/bopa.md` and
  `.claude/skills/bopa/SKILL.md` — that's a separate cycle (forge report
  P2). Same for `verify-llm-connections.sh` (P3).
- **No mirror PR upstream.** This filter depends on rm-memory + the
  specific compose layout — it's a fork-only feature.

## Verification plan

1. **Unit tests** (`pytest rm-tools/tests/test_bopa_inlet_filter.py`):
   - Selection logic: 3 sessions, only 1 with matching owner → that one
     is picked.
   - Selection logic: 3 active sessions for same owner → most recent by
     `updated_at` wins.
   - Selection logic: all sessions `status='completed'` → no injection.
   - Failure: mocked MCP returns 502 → returns body unchanged, no
     exception.
   - Failure: `UserValves.enabled=False` → no MCP call made.
   - Prompt shaping: dependencies_met=[2] → "Volgende fase: 2".
2. **Manual integration smoke**:
   - `docker compose -f docker-compose.rm.yaml up -d`
   - Run `register_assistants.py --token <admin-jwt>` to install the
     filter and attach to `rm-assistent`.
   - Seed one fake BOPA session in `memory.bopa_sessions` for the
     logged-in user.
   - Open a fresh chat with `rm-assistent`, send "hallo".
   - Inspect the OpenAI-format request body in the request log for the
     `ACTIEVE BOPA-SESSIE` block.
3. **Negative path manual**: stop the rm-mcp-memory container, send a
   chat — expect no error, just no injection. Logs should show the
   timeout warning.

## Estimated breakdown

| Step                                                                                 | Time   |
| ------------------------------------------------------------------------------------ | ------ |
| Filter source + Valves + caching                                                     | 25 min |
| Registrar wiring (`FILTERS` list + `register_filter` POST helper + `meta.filterIds`) | 15 min |
| Unit tests (6 cases)                                                                 | 15 min |
| Docs page                                                                            | 10 min |
| Local smoke + tweaks                                                                 | 15 min |

Total: ~80 minutes. Sits inside the medium-cycle budget; no part is
research-shaped.
