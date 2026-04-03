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
