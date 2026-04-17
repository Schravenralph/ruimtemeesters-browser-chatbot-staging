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

---

## Resolution

**Status:** FIX PROPOSED 2026-04-17 in [Riens-Sales-Viewer#8](https://github.com/Schravenralph/Waar-Zitten-We-GeoTool/pull/8) (repo slug: `Waar-Zitten-We-GeoTool`).

### Root cause

`server/src/app.ts` declared `GET /health` **after** `app.use(authMiddleware)`. In production the middleware returns **HTTP 503** for any unauthenticated request that doesn't match an anon-route prefix — which included `/health`. So Docker's HEALTHCHECK (`wget --spider http://localhost:3001/health`) received 503 and flagged the container unhealthy.

The relevant lines (pre-fix):

- `server/src/app.ts:49`  → `app.use(authMiddleware)`
- `server/src/app.ts:55`  → `app.get('/health', ...)` (gated)
- `server/src/middleware/auth.ts:40` → the `return res.status(503)` that fired

The suspicion about `GRAPHQL_API_KEY` in the original issue was a red herring — it only affects GraphQL requests, not `/health`.

### Current workaround (to be removed after merge)

`ALLOW_MOCK_AUTH_IN_PRODUCTION=true` is set in prod env, which bypasses the 503 branch of `authMiddleware`. Side effect: every anonymous request gets director-role mock auth, which is undesirable for a production deployment.

### Fix

Move the `/health` route above `authMiddleware` so liveness probes don't require credentials. Standard practice — Docker HEALTHCHECK and Caddy/k8s liveness probes have no way to supply auth headers.

Regression test added at `server/tests/health.test.ts` that exercises the exact production + mock + no-override triplet.

### Verification

- Jest: 2/2 health tests pass; full suite: no new failures (6 pre-existing, unrelated)
- Live: `docker cp` of patched `app.ts` into `sales-viewer-api` + tsx auto-reload; `/health` returns 200; container stays `healthy`

### Post-merge ops follow-up

After the fix is deployed, set `ALLOW_MOCK_AUTH_IN_PRODUCTION=` (empty) in the production env and confirm:
- `/health` still returns 200
- Any `/api/*` request without a `SERVICE_API_KEY` match returns 503 (intended)
