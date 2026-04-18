# MCP Servers: Auth & Corrections — Design Spec

**Date:** 2026-04-02
**Status:** Implemented
**Supersedes:** `2026-04-01-phase-c-mcp-extension-layer.md` (for implementation details — architecture decisions remain valid)

---

## Context

The MCP servers monorepo (`/home/ralph/Projects/Ruimtemeesters-MCP-Servers/`) is built and functional: 8 servers, 48 tools, shared package with HTTP client + stdio/HTTP transport. However, the servers were built from an early spec that had incorrect ports, API paths, and incomplete auth. This spec captures the corrections needed.

## Goal

1. Fix port and API path mismatches so MCP servers hit the correct backend endpoints
2. Add API key auth to all MCP servers (consistent `X-API-Key` on every request)
3. Add API key middleware to Sales Predictor (the only backend missing it)
4. Clean up minor code quality issues (Riens raw fetch)

## Non-Goals

- JWT/Clerk auth forwarding (can be layered later if needed)
- SSE transport changes (already working)
- New tools or tool behavior changes
- OpenWebUI MCP client integration (Phase C4, separate work)

---

## 1. Port & Path Corrections

### Default URL changes in MCP servers

| Server          | Current Default         | Correct Default             | File                                     |
| --------------- | ----------------------- | --------------------------- | ---------------------------------------- |
| TSA             | `http://localhost:8000` | `http://localhost:8100`     | `packages/tsa/src/server.ts`             |
| Geoportaal      | `http://localhost:3000` | `http://localhost:5002/api` | `packages/geoportaal/src/server.ts`      |
| Dashboarding    | `http://localhost:3003` | `http://localhost:5022`     | `packages/dashboarding/src/server.ts`    |
| Riens           | `http://localhost:7707` | `http://localhost:3001`     | `packages/riens/src/server.ts`           |
| Sales Predictor | `http://localhost:8001` | `http://localhost:8000`     | `packages/sales-predictor/src/server.ts` |

Databank (4000), Opdrachten (6300), and Aggregator (6000) are already correct.

### TSA API path corrections

All 6 TSA endpoints need `/v1/` inserted:

| Current Path                  | Correct Path                     |
| ----------------------------- | -------------------------------- |
| `/api/forecast/bevolking`     | `/api/v1/forecast/bevolking`     |
| `/api/forecast/{geo_code}`    | `/api/v1/forecast/{geo_code}`    |
| `/api/backtest/bevolking`     | `/api/v1/backtest/bevolking`     |
| `/api/diagnostics/{geo_code}` | `/api/v1/diagnostics/{geo_code}` |
| `/api/gemeenten`              | `/api/v1/gemeenten`              |
| `/api/models/status`          | `/api/v1/models/status`          |

### Claude Code config

`claude-code-config.json` needs matching URL updates for all 5 servers above.

---

## 2. Auth: API Key for All Servers

### Strategy

Every MCP server sends `X-API-Key` on every request. Each backend validates against its `SERVICE_API_KEY` env var. If the env var isn't set on the backend, auth is skipped (backwards compatible).

### Backend auth status

| Backend App     | Has `SERVICE_API_KEY` Middleware | Framework      | Middleware Location                        |
| --------------- | -------------------------------- | -------------- | ------------------------------------------ |
| Databank        | Yes                              | Express/TS     | Already has it                             |
| Geoportaal      | Yes                              | Express/TS     | `src/server/middleware/auth.middleware.ts` |
| TSA             | Yes                              | Express/TS     | Already has it                             |
| Dashboarding    | Yes                              | Express/TS     | `src/server/middleware/auth.ts`            |
| Riens           | Yes                              | Express/TS     | `server/src/middleware/auth.ts`            |
| Sales Predictor | **No**                           | FastAPI/Python | Needs new middleware                       |
| Opdrachten      | Yes                              | Express/TS     | `src/api/auth.ts`                          |
| Aggregator      | Yes                              | Express/TS     | Already has it                             |

**Only Sales Predictor needs backend changes.**

### MCP server auth wiring

Each MCP server needs to read its API key from an env var and pass it to `HttpOptions.apiKey`. Three servers already do this (Databank, TSA, Aggregator). Five need it added:

| MCP Server      | Env Var to Add            | File                                     |
| --------------- | ------------------------- | ---------------------------------------- |
| Geoportaal      | `GEOPORTAAL_API_KEY`      | `packages/geoportaal/src/server.ts`      |
| Dashboarding    | `DASHBOARDING_API_KEY`    | `packages/dashboarding/src/server.ts`    |
| Riens           | `RIENS_API_KEY`           | `packages/riens/src/server.ts`           |
| Sales Predictor | `SALES_PREDICTOR_API_KEY` | `packages/sales-predictor/src/server.ts` |
| Opdrachten      | `OPDRACHTEN_API_KEY`      | `packages/opdrachten/src/server.ts`      |

Pattern (already used by Databank/TSA/Aggregator):

```typescript
const API_KEY = process.env.GEOPORTAAL_API_KEY ?? '';
const opts: HttpOptions = { baseUrl: API_URL, apiKey: API_KEY };
```

### Sales Predictor backend — add API key middleware

**Repo:** `/home/ralph/Projects/Sales-Predictor/`
**Framework:** FastAPI (Python)
**Entry point:** `backend_api.py`

Add a FastAPI HTTP middleware that:

1. Reads `SERVICE_API_KEY` from env at startup
2. If set, requires `X-API-Key` header to match on all routes except `/health` and `/docs`
3. If not set, passes through (backwards compatible)
4. Returns 401 JSON `{"detail": "Invalid or missing API key"}` on mismatch
5. Uses `hmac.compare_digest()` for timing-safe comparison

Implementation: `@app.middleware("http")` in `backend_api.py` (keeps it simple, no separate file needed for a single middleware).

---

## 3. Code Quality Fix

### Riens: replace raw fetch with shared helper

`packages/riens/src/server.ts` — the `update_gemeente` tool uses raw `fetch()` instead of the shared HTTP client.

**Fix:** Add `apiPut()` to `packages/shared/src/http.ts` (same pattern as `apiPost`, but `method: 'PUT'`), then use it in the Riens server.

---

## 4. Config Updates

### .env.example (MCP repo)

Add all API key env vars:

```env
# App API URLs
DATABANK_API_URL=http://localhost:4000
GEOPORTAAL_API_URL=http://localhost:5002/api
TSA_API_URL=http://localhost:8100
DASHBOARDING_API_URL=http://localhost:5022
RIENS_API_URL=http://localhost:3001
SALES_PREDICTOR_API_URL=http://localhost:8000
OPDRACHTEN_API_URL=http://localhost:6300
AGGREGATOR_API_URL=http://localhost:6000

# API Keys
DATABANK_AUTH_TOKEN=
GEOPORTAAL_API_KEY=
TSA_API_KEY=
DASHBOARDING_API_KEY=
RIENS_API_KEY=
SALES_PREDICTOR_API_KEY=
OPDRACHTEN_API_KEY=
AGGREGATOR_API_KEY=
```

### claude-code-config.json

Update all server entries with correct URLs and add API key env vars.

---

## 5. Current Tool Inventory (for reference)

The spec this supersedes listed 46 tools across 8 servers. The actual count is **48 tools** because Databank was expanded:

| MCP Server      | Tool Count | Tools                                                                                                                                                                                                   |
| --------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Databank        | **9**      | beleidsscan_query, get_document, search_documents, browse_knowledge_graph, get_entity, start_beleidsscan, get_workflow_status, get_databank_stats, list_municipalities                                  |
| Geoportaal      | 6          | query_spatial_rules, get_air_quality, get_weather, get_building_data, search_documents, search_pdok                                                                                                     |
| TSA             | 6          | run_population_forecast, get_forecast_results, run_backtest, get_diagnostics, list_gemeenten, get_model_status                                                                                          |
| Dashboarding    | 4          | get_dashboard_data, get_statistics, get_trends, search_dashboard                                                                                                                                        |
| Riens           | 2          | get_gemeente_status, update_gemeente                                                                                                                                                                    |
| Sales Predictor | 4          | run_sales_forecast, get_predictions, compare_models, list_models                                                                                                                                        |
| Opdrachten      | 7          | get_inbox, get_pipeline, get_pipeline_deadlines, search_library, get_stats, accept_inbox_item, move_pipeline_stage                                                                                      |
| Aggregator      | 10         | context_at_coordinate, context_municipality, search_documents, get_document_summary, spatial_rules_at_point, solar_potential, search_knowledge_graph, get_entity_relations, traverse_graph, graph_stats |
| **Total**       | **48**     |                                                                                                                                                                                                         |

---

## 6. Files Changed Summary

### MCP Servers repo (`Ruimtemeesters-MCP-Servers`)

| File                                     | Change                                 |
| ---------------------------------------- | -------------------------------------- |
| `packages/tsa/src/server.ts`             | Port 8100, add `/v1/` to all 6 paths   |
| `packages/geoportaal/src/server.ts`      | Port 5002/api, add API key             |
| `packages/dashboarding/src/server.ts`    | Port 5022, add API key                 |
| `packages/riens/src/server.ts`           | Port 3001, add API key, use `apiPut()` |
| `packages/sales-predictor/src/server.ts` | Port 8000, add API key                 |
| `packages/opdrachten/src/server.ts`      | Add API key                            |
| `packages/shared/src/http.ts`            | Add `apiPut()`                         |
| `packages/shared/src/index.ts`           | Export `apiPut`                        |
| `.env.example`                           | Correct URLs, add all API key vars     |
| `claude-code-config.json`                | Correct URLs, add API key env vars     |

### Sales Predictor repo (`Sales-Predictor`)

| File             | Change                                |
| ---------------- | ------------------------------------- |
| `backend_api.py` | Add `SERVICE_API_KEY` HTTP middleware |
