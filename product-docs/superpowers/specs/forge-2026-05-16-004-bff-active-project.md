# Forge Spec: BFF endpoint for active project

**Cycle:** 4 | **Clock:** 0.8h elapsed | **Size:** small

## What

Add `GET /api/v1/rm-memory/active-project?chat_id=<id>` to the user-facing BFF (`backend/open_webui/routers/rm_memory.py`). Proxies the rm-memory MCP's `get_active_project` tool, forwarding the chat id as `X-Thread-Id`. Returns the active project row (`{project_id, kind, label, set_at}`) or `null` when no project is bound to the chat.

## Why

The model now sets active projects (cycle 3) but the frontend can't read them. Cycle 5 will add the chat-header pill that consumes this endpoint. This cycle ships the infrastructure that cycle 5 depends on.

## Success criteria

1. New endpoint returns the active project for a (user, chat) pair, or `null` when none.
2. `chat_id` query param is forwarded as `X-Thread-Id` to the MCP.
3. Auth: gateway token + caller email as `X-Forwarded-User`, same as existing endpoints.
4. Tests cover: happy path, null response, missing chat_id (400), 502 propagation from MCP.
5. `_call_user_tool` extended to optionally carry `X-Thread-Id` — backward-compatible for existing endpoints that don't use it.

## Approach

- Extend `_call_user_tool(*, tool_name, arguments, user_email, x_thread_id=None)` — only set the header when present.
- Add `ActiveProjectOutput` Pydantic model mirroring the MCP's `getActiveProject` output.
- Add `GET /active-project` endpoint with required `chat_id: str = Query(..., min_length=1, max_length=128)`.
- Mirror existing test fixtures + add 4 new tests.

## Not doing

- `POST /active-project` / `DELETE /active-project` — `set_active_project` is meant to be called by the model from chat context (via the SKILL.md instruction); manual UI binding can ship later when the pill needs it.
- Live refresh / websocket push of active-project changes — cycle 5's pill will refetch on chat switch.
- Frontend changes — strictly BFF in this cycle.
