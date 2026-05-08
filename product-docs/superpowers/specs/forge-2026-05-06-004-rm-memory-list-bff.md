# Forge Spec: User-facing rm-memory `list` BFF

**Cycle:** 4 | **Clock:** ~0.5h elapsed | **Size:** medium

## What

A new authenticated endpoint `GET /api/v1/rm-memory/list?scope=&project_id=&type=&limit=` that proxies the rm-memory MCP's `list_memories` tool. The chatbot resolves the calling user from the existing OpenWebUI session, forwards their email as `X-Forwarded-User`, and authenticates to the MCP with `MEMORY_GATEWAY_TOKEN`. Returns the typed `ListMemoriesOutput` (entries with name/type/scope/description/owner_user_id/project_id/updated_at, sorted by recency).

## Why

Issue #47 (user-facing memory panel) needs a BFF the frontend can read from. Today there is no chatbot-side endpoint that returns a user's own rm-memory entries — the only paths to that data go through Claude Desktop or direct MCP curl. This BFF is the read-side foundation that future cycles wire a Svelte panel onto. Splitting list-side from CRUD keeps the cycle medium and lets the panel cycle land sooner.

## Success criteria

1. `GET /api/v1/rm-memory/list` requires auth (`get_verified_user`); unauthenticated → 401.
2. Outbound MCP request carries `Authorization: Bearer $MEMORY_GATEWAY_TOKEN` AND `X-Forwarded-User: <user.email>`. Asserted in test.
3. Optional query params (`scope` ∈ {`user`, `project`, `global`}, `project_id`, `type`, `limit` 1-200) forward as MCP arguments; absent params are NOT fabricated.
4. The MCP applies its Session 1 read predicate (user own + global + project) — the BFF doesn't filter post-hoc.
5. Configured via the existing `MEMORY_GATEWAY_TOKEN` and `RM_MEMORY_MCP_URL` env vars (no new env). When the gateway token is absent the endpoint returns 503 with a clear "MEMORY_GATEWAY_TOKEN not configured" detail.
6. Failure shapes (502 / timeout / malformed body / JSON-RPC error envelope) propagate as 502 with detail.

## Approach

- Reuse `backend/open_webui/utils/mcp_response.py` (cycle 2's parser).
- New router `backend/open_webui/routers/rm_memory.py` mirroring `admin_memory.py` but: gateway token instead of admin, X-Forwarded-User present, `get_verified_user` instead of `get_admin_user`.
- Pydantic response models mirroring `ListMemoriesOutput`.
- Unit test mirroring `test_admin_memory.py`: 9-10 tests covering happy path, header shape, optional-arg passthrough, 502/timeout/malformed/error-envelope failures, missing-gateway-token guard.
- Don't ship CRUD (`get_memory`, `save_memory`, `forget_memory`) in this cycle — read-only first; CRUD is the next forge cycle.

## Not doing

- POST/DELETE endpoints — separate cycle (mutations need more careful UX + auth audit).
- Frontend route — separate cycle.
- Caching — interactive use, refresh-on-open is fine.
- A new env var for the user-facing token — `MEMORY_GATEWAY_TOKEN` already exists and is the right one.
- Email-fallback if `user.email` is missing — match `bopa_session_context` behavior (no `X-Forwarded-User`, MCP returns 401, BFF surfaces 502 with the MCP message).
