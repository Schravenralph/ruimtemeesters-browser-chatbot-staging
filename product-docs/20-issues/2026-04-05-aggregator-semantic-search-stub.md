# Aggregator Semantic Search Is Still a Stub

**Date:** 2026-04-05
**Severity:** medium
**Service:** Ruimtemeesters-Aggregator
**Phase found:** benchmark

## Description

The Aggregator's `/v1/search/semantic` and `/v1/search/hybrid` endpoints are stubs that fall back to `ILIKE` title matching on PostgreSQL. The Databank has a real hybrid vector+keyword search at `/api/search` that uses embeddings and returns ranked content chunks with KG-enriched `relatedEntities`.

## Impact

MCP tools using `search_documents` go through the Aggregator's document search (which uses PostgreSQL `ts_rank`), not the Databank's better semantic search. Answer quality is limited by keyword matching rather than semantic similarity.

## Fix

Proxy the Aggregator's semantic/hybrid search endpoints to the Databank's `/api/search` endpoint via HTTP, similar to the KG proxy fix done on 2026-04-05.

## Resolution

**Date:** 2026-04-06

Aggregator search endpoints now proxy to Databank `GET /api/search` (real hybrid vector+keyword+KG search). Municipality names in queries trigger automatic Geoportaal spatial rule enrichment. The old `POST /v1/documents/search` was renamed to `POST /v1/search/metadata-search` with a 308 redirect for backwards compatibility.
