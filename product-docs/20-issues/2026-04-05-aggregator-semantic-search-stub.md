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

---

## Re-verification 2026-04-17

Confirmed live on `ruimtemeesters-aggregator`:

```
POST /v1/search/semantic  — HTTP 200 in ~230ms (documents + relatedEntities returned)
POST /v1/search/hybrid    — HTTP 200 in ~190ms (same handler, `searchType: "hybrid"`)
POST /v1/search/metadata-search — HTTP 200 with FTS ranking
```

Implementation confirmed at `Ruimtemeesters-Aggregator/src/routes/semantic-search.ts:52-101`:

- `handleSearch` proxies to Databank `GET /api/search` via `databankGet<DatabankSearchResponse>('/api/search', { params })`
- Parallel spatial enrichment via `fetchSpatialRulesAtPoint` when `detectMunicipality(q)` finds a gemeente name in the query
- Both `/semantic` and `/hybrid` route to the same handler (Databank's search is already hybrid vector+keyword)

### Content-quality footnote (not a regression)

Spot-check results show some document chunks containing GML/KML coordinate blobs rather than clean text. That's a **chunking-quality** issue (see `2026-04-05-databank-chunk-quality-too-small.md`) — not an aggregator-wiring issue. Fix lives downstream in the Databank ingestion pipeline.

Issue remains resolved for the "is the endpoint actually proxying?" question. Closing for real.
