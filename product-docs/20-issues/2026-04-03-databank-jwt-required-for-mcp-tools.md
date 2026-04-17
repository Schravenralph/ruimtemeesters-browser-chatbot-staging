# Databank MCP Tools — JWT Required in Addition to API Key

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-Databank + MCP Databank Server
**Phase found:** 3

## Description

The Databank API requires both API key auth AND JWT token for document routes. The MCP server sends the API key (which now validates), but doesn't send a JWT. The document routes return "No token provided" after API key auth passes.

## Chain of auth

1. Chatbot → MCP Server: X-API-Key header (works)
2. MCP Server → Databank Backend: X-API-Key header (works after registering key in DB)
3. Databank Backend: API key validates, but document router also requires JWT → "No token provided"

## Fix options

1. **Make API key sufficient for MCP routes** — if API key is valid, skip JWT check for service-to-service calls
2. **Have MCP server generate/forward a service JWT** — create a service account token
3. **Add a bypass flag** — when request comes with valid API key, treat as authenticated service

This is the same issue noted in project memory: "direct app tools need Clerk JWT fix".

---

## Resolution

**Status:** RESOLVED on 2026-04-03 via `Ruimtemeesters-Databank@cde5c79d1a`.

The fix was "accept API key as auth in authenticate middleware" — same day as the filing. `src/server/middleware/authMiddleware.ts:33-46` now checks `X-API-Key` as *Strategy 0* (before JWT), and if the key validates via `ApiKey.validate(...)`, it treats the caller as an authenticated service account (`userId: service:<keyname>`, `role: admin`) and short-circuits the JWT branch. MCP calls carrying the X-API-Key header no longer hit the "No token provided" path.

Live verification (2026-04-17, with the chatbot's `DATABANK_AUTH_TOKEN` used as `X-API-Key`):

| Endpoint | Status | Notes |
|---|---|---|
| `GET /health` | 200 | baseline |
| `GET /api/search?q=test` | 200 | returns real documents, auth passed |
| `GET /api/knowledge-graph?limit=1` | 200 | returns KG nodes, auth passed |
| `GET /api/stats/documents` | 200 | 26,789 documents counted, auth passed |
| `GET /api/canonical-documents/1` | 400 (validation) | auth passed; 400 is "invalid ID format" |
| `POST /api/pipeline/query` (MCP's main entry) | 200 after 24.4s | auth passed; latency is a separate perf concern |

No "No token provided" or auth-related 401/403 anywhere.

### Follow-up worth filing

`POST /api/pipeline/query` returns 200 but takes ~24s even with `decompose=false, includeKg=false` (searchMs=2342, kgMs=22071). If the chatbot's MCP client has a tight timeout (per `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA=10s` default in OpenWebUI), the user-visible effect is still "MCP tool fails" even though auth is green. That's a **pipeline performance issue**, not the auth issue this doc covers. Suggest filing a new ticket focused on the kg phase's 22s on a no-op query.

Closing this issue as resolved.
