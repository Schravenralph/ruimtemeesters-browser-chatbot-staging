# Databank CSRF Blocks Service-to-Service POST Requests

**Date:** 2026-04-05
**Severity:** medium
**Service:** Ruimtemeesters-Databank
**Phase found:** benchmark

## Description

The Databank's POST endpoints (`/api/knowledge-graph/traverse`, `/api/knowledge-graph/graphrag-query`, etc.) reject requests authenticated only via `X-API-Key` header with a CSRF validation error: `"Session invalid or expired. Please refresh the page."`

GET endpoints work fine with API key auth. Only POST endpoints are affected.

## Impact

The Aggregator's BFS traversal workaround (iterative GET calls to entity/:id) works but is slower and limited to 10 neighbors per entity. The proper traverse, path, and graphrag-query endpoints can't be used service-to-service.

## Fix

Skip CSRF validation when the request is authenticated via `X-API-Key` (service-to-service auth). CSRF protection is only needed for browser sessions with cookies.
