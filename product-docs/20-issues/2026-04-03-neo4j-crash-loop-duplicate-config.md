# Neo4j Crash Loop — Duplicate Config Key

**Date:** 2026-04-03
**Severity:** critical
**Service:** Ruimtemeesters-Databank (Neo4j)
**Phase found:** 1

## Description

Neo4j container (`ruimtemeesters-databank-neo4j`) is in a crash/restart loop. On every startup, the APOC plugin installer appends `dbms.security.procedures.unrestricted` to `neo4j.conf`. After multiple restarts, this key is declared multiple times, which Neo4j treats as a fatal config error.

## Repro steps

1. `docker logs ruimtemeesters-databank-neo4j --tail 20`
2. Observe repeated "Failed to read config: dbms.security.procedures.unrestricted declared multiple times"

## Expected

Neo4j starts successfully and accepts bolt connections on port 7687.

## Actual

Container restarts every few seconds with config parse error. This cascades to:

- Databank backend FATAL: cannot connect to Neo4j
- Any tool that queries the knowledge graph fails

## Notes

Root cause is in the Neo4j Docker entrypoint or the APOC plugin installation script. Each restart re-runs the plugin installer which appends to the config file, creating duplicates.

Fix options:

1. Mount a custom `neo4j.conf` that already includes the APOC config (prevents the installer from adding it)
2. Clear the config file before each startup via an entrypoint wrapper
3. Use a Neo4j image version that handles APOC config idempotently

---

## Resolution

**Status:** RESOLVED on 2026-04-03 via `Ruimtemeesters-Databank@e552006205`.

Fix was landed the same day this issue was filed. The commit adds two env vars in `docker-compose.yml` (Databank repo):

```yaml
- NEO4J_dbms_security_procedures_unrestricted=apoc.*
- NEO4J_dbms_security_procedures_allowlist=apoc.*
```

Root cause was confirmed: when `NEO4J_PLUGINS=["apoc"]` is set without the matching config env vars, Neo4j 5.x's entrypoint installs the APOC jar and appends the allowlist config to `/var/lib/neo4j/conf/neo4j.conf`. Without a persisted `/conf` mount, this is idempotent-enough for first-run; but if `/conf` ever gets persisted (or the entrypoint re-runs inside the same container), the append duplicates the key and Neo4j refuses to start. Declaring the config via `NEO4J_*` env vars makes the entrypoint skip the conf append entirely.

**Verification 2026-04-17:**

- `/conf` is NOT in the volumes list (checked via `docker inspect`)
- Stress-tested `docker restart ruimtemeesters-databank-neo4j` ×3; `grep -c "^dbms.security.procedures.unrestricted" neo4j.conf` returns `1` after each restart
- Container has been `Up 3+ days (healthy)` before stress test

This issue doc was filed but never updated with the resolution; closing now. The companion backend-unhealthy issue resolves transitively.
