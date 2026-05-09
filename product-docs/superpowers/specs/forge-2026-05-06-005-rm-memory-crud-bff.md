# Forge Spec: rm-memory CRUD BFF (get / save / forget)

**Cycle:** 5 | **Clock:** ~1.0h elapsed | **Size:** medium-large

## What

Extend `backend/open_webui/routers/rm_memory.py` with three new endpoints that proxy the rm-memory MCP's `get_memory`, `save_memory`, and `forget_memory` tools:

- `GET /api/v1/rm-memory/{name}?type=&project_id=` — fetch one entry, full content.
- `POST /api/v1/rm-memory/` — body `{name, description, type, content, scope?, project_id?}`. Creates or upserts.
- `DELETE /api/v1/rm-memory/{name}?type=&scope=&project_id=` — hard-delete one entry.

All three carry `Authorization: Bearer $MEMORY_GATEWAY_TOKEN` + `X-Forwarded-User: <user.email>`. The MCP applies its own scope guards — the BFF stays a pass-through.

## Why

Cycle 4 shipped read-side; the user-facing memory panel (#47) needs writes too — edit ("forget + save") and delete actions are the difference between a viewer and a real management UI. Without these, the panel cycle would launch with read-only and no follow-up path. Shipping CRUD now keeps the panel cycle scope-clean (purely UI work).

## Success criteria

1. All three endpoints require auth (`get_verified_user`); unauth → 401.
2. `save_memory` enforces the MCP's `scope='project' ↔ project_id` invariant client-side via Pydantic so a 422 from the chatbot is clearer than the MCP's downstream error. Specifically: project_id required when scope='project'; project_id MUST be absent for other scopes.
3. `get_memory` returns full content (the index view's `description` is replaced by the row's `content`).
4. `forget_memory` returns `{deleted: bool, rows: number}` from the MCP; the BFF doesn't try to second-guess "0 rows means 404" — that's an MCP semantics decision.
5. All three propagate transport / parser / error-envelope failures as 502 (matching cycle 2/4 patterns).
6. New unit tests (5-7) covering each endpoint's happy path + arg passthrough + auth shape; no DB / no FastAPI test client.

## Approach

- Reuse `_call_*` pattern from cycle 4: a single helper that takes the tool name + arguments and returns the parsed payload. Refactor `_call_list_memories` into a generic `_call_user_tool(name, arguments, user_email)` so the four endpoints share one transport function.
- Three new Pydantic request/response models. The save request uses a Pydantic `model_validator` to enforce the project_id invariant.
- Body for `save_memory` is JSON; query params for `get`/`forget` so URLs stay shareable.
- The encoded `{name}` path parameter — names are user-controlled and may contain slashes / special chars. Use FastAPI's `path: str = Path(...)` with `name: str = Path(..., min_length=1, max_length=120)` matching the MCP schema. URL-decode is automatic.

## Not doing

- Bulk import / export — out of scope for #47.
- Optimistic concurrency / ETag — single-writer admin-style use.
- Soft-delete — `forget_memory` is hard-delete by design; that's the MCP's decision.
- Frontend — that's cycle 6 (panel UI).
- Caching — interactive use, refresh-on-action is fine.
