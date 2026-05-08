# Forge Spec: Admin memory adoption-stats — backend BFF

**Cycle:** 2 | **Clock:** ~0.1h elapsed | **Size:** medium

## What

A new admin-only HTTP endpoint `GET /api/v1/admin/memory/stats?since_days=N` on the chatbot backend that proxies the memory MCP's `get_adoption_stats` tool and returns the parsed `GetAdoptionStatsOutput` envelope. Auth: chatbot admin role (existing `get_admin_user` dependency). Outbound: `Authorization: Bearer $MEMORY_ADMIN_TOKEN` to `RM_MEMORY_MCP_URL` — the admin token is server-side only and never reaches the browser.

## Why

`get_adoption_stats` is the canonical answer to "is anyone using memory yet?" but reaching it today means SSH to prod, mint a JWT, and curl the MCP. That barrier is high enough that nobody checks. Issue #48 proposes a UI; this cycle builds the BFF the UI will read from. Splitting the BFF into its own cycle keeps each piece in the medium-cycle sweet spot, and the BFF is independently observable (curl), so future-cycle UI work isn't blocked on backend questions like "what does the response actually look like?"

## Success criteria

1. `GET /api/v1/admin/memory/stats` returns 403 for non-admin chatbot users.
2. With admin auth, returns the parsed `GetAdoptionStatsOutput` JSON envelope (`{measured_at, entries:{...}, session_events:{...}, bopa_sessions:{...}, projects, users}`) — verified end-to-end against the live MCP via curl, OR with a mocked unit test that asserts the right RPC envelope is sent and the right Pydantic shape comes back.
3. Optional `since_days` query param (1-90, default 7) is forwarded as the MCP tool's `since_days` argument.
4. Browser-supplied auth never appears on the outbound MCP call — the admin token comes from `MEMORY_ADMIN_TOKEN` env only. Asserted in the test.
5. MCP failures (502, timeout) propagate as 502 with a clear detail; the chatbot doesn't 500 or hang.
6. New router registered in `main.py` under `/api/v1/admin/memory`.

## Approach

- New file `backend/open_webui/routers/admin_memory.py` with an `APIRouter` and one endpoint.
- Reuse the SSE-or-JSON parser pattern from `rm-tools/filters/bopa_session_context._parse_mcp_response` (duplicated rather than imported — it's pure, ~30 lines, and rm-tools isn't on the chatbot backend's import path). Pull it into a small module in `backend/open_webui/utils/mcp_response.py` so future admin endpoints can share it.
- httpx async client with `timeout=10.0`. Single retry not needed — admin endpoints are interactive, not background.
- Env vars: `MEMORY_ADMIN_TOKEN` (already known to the operator from MCP-Servers compose) + `RM_MEMORY_MCP_URL` (default `http://rm-mcp-memory:3200/mcp`). Documented in `.env.rm.example`.
- Pydantic response model mirroring the typed `GetAdoptionStatsOutput` so the FastAPI auto-docs render the shape.
- Test: mock httpx.AsyncClient, assert outbound RPC envelope (tools/call name + arguments + Authorization header) and parsed response. Cover the happy path, the 502 propagation, and the no-admin-token-configured case (return 503 with a clear "MEMORY_ADMIN_TOKEN not configured" detail).

## Not doing

- Frontend route — separate cycle.
- Caching — admin will hit this manually a few times a day; no need.
- Rate limiting — internal admin endpoint, not exposed to the public.
- Memory MCP-side changes — the tool already exists.
- Time-series data from `memory.adoption_stats_log` — depends on MCP-Servers#75 (recorder), not yet built. Current snapshot is enough for now.
