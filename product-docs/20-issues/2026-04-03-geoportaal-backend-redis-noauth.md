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
