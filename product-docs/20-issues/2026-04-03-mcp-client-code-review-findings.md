# MCP Client Code Review Findings

**Date:** 2026-04-03
**Severity:** medium
**Service:** Ruimtemeesters-Browser-Chatbot (MCP Client)
**Phase found:** 2 (code review)

## Files reviewed

- `backend/open_webui/utils/mcp/client.py` — MCP client class
- `backend/open_webui/utils/middleware.py:2460-2600` — MCP client usage in request middleware

## Findings

### 1. SSL Bypass Logic (low risk for local dev, medium for production)

**File:** `client.py:15-32, 43-49`

When `AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL` is `False`, the client creates an httpx client with `verify=False`. This disables all SSL certificate verification for MCP server connections.

- For local dev (all services on Docker network): acceptable
- For production: should be restricted. Currently it's a global toggle — either all SSL is verified or none is.
- The env var defaults to `True` (line 760 of env.py), so production is safe by default.

**Recommendation:** No action needed for local dev. For production, consider per-server SSL config rather than a global toggle.

### 2. No Timeout on Tool Calls (medium)

**File:** `client.py:90`

`call_tool` has no timeout wrapper. If an MCP server hangs, the request to the chatbot will hang indefinitely. The `connect` method has a 10-second timeout via `anyio.fail_after(10)`, but `call_tool` and `list_tool_specs` don't.

**Recommendation:** Wrap `call_tool` with `anyio.fail_after(30)` or similar. Long-running tools (like forecasting) may need longer timeouts, but a default prevents infinite hangs.

### 3. Disconnect Error Handling (low)

**File:** `client.py:126-128`

`disconnect()` calls `self.exit_stack.aclose()` without checking if `exit_stack` is `None`. If `connect()` fails before setting `exit_stack`, `disconnect()` will raise `AttributeError`.

**Recommendation:** Add a null check: `if self.exit_stack: await self.exit_stack.aclose()`.

### 4. Custom Headers Passed Correctly (good)

**File:** `middleware.py:2525-2528`

The `X-API-Key` headers from `TOOL_SERVER_CONNECTIONS` config are correctly merged into the connection headers. Auth type handling is comprehensive (bearer, none, session, oauth).

### 5. User Info Header Forwarding (good)

**File:** `middleware.py:2531-2536`

User info and chat/message IDs are forwarded to MCP servers when enabled. This supports audit logging in backend services.

### 6. MCP Client Per-Request Lifecycle (correct but expensive)

**File:** `middleware.py:2538-2542`

A new MCPClient is created and connected per request. This means every chat message that uses a tool opens a new HTTP connection to the MCP server, initializes the session, lists tools, calls the tool, then disconnects.

For a production system with heavy usage, this would benefit from connection pooling. For current scale, it's fine.

## Summary

No critical issues. The MCP client is functional and correctly wired. The main improvements would be:
1. Add timeouts to tool calls
2. Add null check in disconnect
3. Consider connection pooling for scale (future)

---

## Resolution

**Partial — findings #2 and #3 fixed on branch `fix/mcp-client-hardening`. Findings #1, #4, #5, #6 deferred / informational.**

### Finding #2 (no timeout on tool calls) — FIXED

`call_tool` and `list_tool_specs` are now wrapped in `anyio.fail_after(_MCP_CALL_TIMEOUT)`. Timeout defaults to `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA * 3` (~30s with the 10s repo default) — reuses the existing tool-server timeout knob rather than introducing a new one. MCP sessions have more overhead than a single HTTP request, so 3x gives headroom for handshake + list + call.

### Finding #3 (null AttributeError on disconnect) — FIXED

`disconnect()` now checks `self.exit_stack is not None` before calling `aclose()`, and resets both `exit_stack` and `session` to `None` so subsequent calls are no-ops. This matters because `connect()`'s except handler invokes `disconnect()` via `asyncio.shield`; previously, if `connect` failed before line 60 (where `exit_stack` gets assigned), the AttributeError replaced the real upstream exception and masked it from the caller.

Regression test added at `backend/open_webui/test/util/test_mcp_client.py` (2/2 pass under pytest inside the container).

### Deferred

- **#1** (per-server SSL config): real prod concern but needs schema change to `TOOL_SERVER_CONNECTIONS`; filing separately once we have a production deployment that needs it.
- **#6** (MCP client per-request lifecycle): correct but expensive. Deferred until measured throughput warrants pooling.
- **#4, #5**: positive findings, no action.
