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
