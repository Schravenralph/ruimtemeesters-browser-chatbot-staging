# Databank /api/pipeline/query — 22s KG phase even when includeKg=false

**Date:** 2026-04-17
**Severity:** high
**Service:** Ruimtemeesters-Databank (Pipeline API) + Ruimtemeesters-Browser-Chatbot (MCP client)
**Phase found:** 4 (during E2E triage of MCP tool failures)

## Description

`POST /api/pipeline/query` is the primary entry point called by the `rm-mcp-databank` MCP server (see `packages/databank/src/server.ts:30` in `Ruimtemeesters-MCP-Servers`). A trivial no-op request with all expensive flags disabled still takes ~24 seconds to return:

```bash
curl -s -o /tmp/body.json -w "HTTP %{http_code}, %{time_total}s\n" \
  -m 30 -X POST "http://localhost:4000/api/pipeline/query" \
  -H "X-API-Key: $DATABANK_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"test","decompose":false,"includeKg":false,"limit":1}'
# HTTP 200, 24.416013s
```

Response breakdown:

```json
{
  "query": "test",
  "pipeline": {"decomposition": false, "kgEnrichment": false},
  "results": [...],
  "metrics": {"searchMs": 2342, "kgMs": 22071, ...}
}
```

## Impact

OpenWebUI's MCP client has a default request timeout of `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA=10s`. Any beleidsscan query through the chatbot's MCP `beleidsscan_query` tool times out far before the 24s pipeline finishes. User-visible: the Beleidsadviseur assistant appears "broken" even though:

- Auth is green (see `2026-04-03-databank-jwt-required-for-mcp-tools.md`, resolved)
- Databank itself eventually returns correct results (HTTP 200, real documents)
- MCP wiring is correct

The MCP code review follow-up in `Ruimtemeesters-Browser-Chatbot#10` (open) bumps the per-call timeout to `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA * 3` (~30s). That's a band-aid — the real fix is making the pipeline fast.

## Suspected root cause

`kgMs: 22071` even though `includeKg=false` means the KG phase is NOT being skipped when the flag says it should be. Suspect places in `Ruimtemeesters-Databank/src/server/routes/pipelineRoutes.ts`:

- Is the `includeKg` branch correctly gated?
- Are `FactFirstRetrievalService` or `GraphRAGRetrievalService` being constructed (with eager Neo4j driver init or embeddings loading) even when not used?
- Is the `ContextualEnrichmentService` doing expensive work per request regardless of flag?

## Fix direction (not implemented yet)

1. Add an early-return in the pipeline when `includeKg === false` — skip KG service construction entirely.
2. Measure the 22s breakdown inside `kgMs`: is it Neo4j cold-start, vector store warming, or a hot-loop query?
3. If KG is meant to always run: profile and fix the slow path (Neo4j query plan, missing index, cold embeddings).
4. Add integration test: `pipeline.query({ includeKg: false })` should return in < 3s on cold cache.

## Repro steps

1. Have a running `rm-mcp-databank` + `ruimtemeesters-databank-backend` (default env)
2. `curl` as above
3. Observe `>20s` response time with `kgMs: >20000` even when flag disables the phase
4. Alternative: trigger the Beleidsadviseur assistant in chatbot.datameesters.nl → observe tool timeout
