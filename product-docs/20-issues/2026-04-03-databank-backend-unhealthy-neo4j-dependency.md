# Databank Backend Unhealthy — Neo4j Dependency

**Date:** 2026-04-03
**Severity:** critical
**Service:** Ruimtemeesters-Databank (Backend)
**Phase found:** 1

## Description

Databank backend (`ruimtemeesters-databank-backend`) exits with FATAL error because it cannot connect to Neo4j. This is a cascading failure from the Neo4j crash loop (see `2026-04-03-neo4j-crash-loop-duplicate-config.md`).

## Repro steps

1. `docker logs ruimtemeesters-databank-backend --tail 20`
2. Observe: "Required connections failed: Neo4j: Failed to connect to server"

## Expected

Backend starts and connects to all dependencies (Postgres, Neo4j, Redis, GraphDB).

## Actual

Postgres, Redis, and GraphDB connections succeed. Neo4j connection fails (DNS resolution fails: `getaddrinfo EAI_AGAIN neo4j`), causing FATAL shutdown.

## Notes

Fix Neo4j first (see companion issue), then restart the backend. The backend requires Neo4j as a mandatory dependency — it will not start in degraded mode.

---

## Resolution

**Status:** RESOLVED transitively on 2026-04-03.

Root cause was the Neo4j crash-loop (see `2026-04-03-neo4j-crash-loop-duplicate-config.md`). Once Neo4j stays up, the backend's Neo4j driver connects and the FATAL no longer fires.

**Verification 2026-04-17:**
```bash
docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "databank-(neo4j|backend)"
#  ruimtemeesters-databank-neo4j     Up … (healthy)
#  (backend container status varies by repo branch state)
```

Closing as a downstream effect of the Neo4j fix; no independent code change was needed in the backend.
