# Geoportaal Backend Unhealthy — Redis NOAUTH

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-Geoportaal (Backend)
**Phase found:** 1

## Description

Geoportaal backend (`geoportaal-backend`) health check fails because it's trying to connect to a Redis instance that requires authentication, but no password is being sent.

## Repro steps

1. `docker logs geoportaal-backend --tail 20`
2. Observe: "ReplyError: NOAUTH Authentication required" on `info` command

## Expected

Backend starts and passes health checks.

## Actual

Repeated Redis NOAUTH errors. The health check uses Redis as a dependency indicator and keeps failing.

## Notes

Investigate:

1. Does Geoportaal's docker-compose define its own Redis, or is it accidentally connecting to Databank's Redis?
2. If it's connecting to Databank's Redis, the Docker network bridge (`databank-network`) may be exposing Redis unintentionally.
3. If Geoportaal needs its own Redis, add one to its docker-compose.
4. If it's connecting to the right Redis but missing the password, add `REDIS_PASSWORD` to Geoportaal's `.env`.

---

## Resolution

**Status:** FIX PROPOSED 2026-04-17 in [Ruimtemeesters-Geoportaal#1069](https://github.com/Schravenralph/Geoportaal/pull/1069).

### Root cause (re-diagnosed)

The filed symptom was "Redis NOAUTH", but recent logs show no NOAUTH errors — that specific regression self-resolved (likely when Geoportaal's own Redis container came up properly on `geoportaal-network` instead of connecting to Databank's password-protected Redis). The `unhealthy` container status remained for a different reason that the filed doc didn't spot:

- Docker HEALTHCHECK and compose healthcheck both probed `/api/health` — the **deep** dependency check at `src/server/controllers/health.controller.ts:39` that aggregates DB + Beleidsscan + GeoNode probes via `Promise.all`.
- `GeonodeService.healthCheck()` uses an axios client with `timeout: 60000` (service default). When `geonode-django` DNS fails with `EAI_AGAIN`, Node's internal DNS retry returns ~5s later.
- `Promise.all` resolves after the slowest branch. Aggregate latency = **~5020 ms**.
- The healthcheck script embeds `setTimeout(() => process.exit(1), 5000)` → fires 20ms before the response arrives → exit 1 → Docker marks unhealthy.

Measured on the running container (2026-04-17):

| Endpoint           | Latency | Result |
| ------------------ | ------- | ------ |
| `/api/health`      | 5020 ms | exit 1 |
| `/api/health/live` | 20 ms   | exit 0 |

### Fix (in the PR above)

1. Dockerfile and compose healthchecks now target **`/api/health/live`** — the liveness probe that was already implemented at `health.controller.ts:58` but unused by container orchestration.
2. `GeonodeService.healthCheck()` now passes `{ timeout: 2000 }` explicitly so `/api/health` total latency is bounded to `max(db, beleidsscan, 2s)` for dashboards that still want the full status.

### Why the Redis part of the original doc no longer applies

Live `docker logs geoportaal-backend --tail 40` has zero `NOAUTH` lines over 2+ hours of runtime. The Geoportaal backend was probably rewired to connect only to `geoportaal-redis` (own network, no password) sometime between the original filing and today. No evidence it's an active problem.

Closing this issue alongside the healthcheck fix.
