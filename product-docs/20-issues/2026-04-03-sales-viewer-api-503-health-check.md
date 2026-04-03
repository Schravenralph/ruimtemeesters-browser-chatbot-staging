# Sales Viewer API — Health Check Returns 503

**Date:** 2026-04-03
**Severity:** high
**Service:** Riens-Sales-Viewer (API)
**Phase found:** 1

## Description

Sales Viewer API (`sales-viewer-api`) is running and accepting requests, but the health check returns HTTP 503. The API itself starts successfully ("API server running on port 3001") and migrations have been applied.

## Repro steps

1. `docker inspect sales-viewer-api --format '{{.State.Health.Status}}'` → unhealthy
2. `docker logs sales-viewer-api --tail 10` → API is running
3. Health check output: "503 Service Unavailable"

## Expected

Health endpoint returns 200.

## Actual

Returns 503. Likely causes:
1. Missing `GRAPHQL_API_KEY` env var (warning in logs: "GRAPHQL_API_KEY not set — GraphQL endpoint will reject all requests")
2. Health endpoint may check downstream dependencies that are unavailable

## Notes

Check:
1. What the health endpoint checks (is it `/health`, `/api/health`, or something else?)
2. Whether `GRAPHQL_API_KEY` is required for the health check to pass
3. Whether the health check depends on external services
