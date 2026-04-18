# ADR-0003: Aggregator boundaries — when to use it vs direct app calls

**Date:** 2026-03-31
**Status:** Accepted

## Context

The chatbot needs to access 8 apps. The Aggregator exists as a gateway but we don't want to route everything through it.

## Decision

**Default:** Call app APIs directly. Each app has its own OpenWebUI Tool.

**Aggregator:** Only for queries that genuinely span multiple apps (Databank + Geoportaal context) or benefit from the Aggregator's specific capabilities (PostGIS spatial joins, Neo4j knowledge graph, cross-database composition).

**No duplication:** If an app has an endpoint, we don't recreate it in the Aggregator.

## Aggregator adds value when

| Use case                                | Why Aggregator                          |
| --------------------------------------- | --------------------------------------- |
| Context at coordinate (beleid + regels) | Parallel queries to 2 DBs, spatial join |
| Municipality overview (docs + rules)    | Cross-database aggregation              |
| Knowledge graph traversal               | Direct Neo4j access                     |
| Solar potential analysis                | PostGIS spatial aggregation             |

## Aggregator does NOT

- Proxy 1:1 to single-app endpoints
- Contain business logic (stays in apps)
- Act as the only way to reach an app
- Duplicate existing app endpoints

## Consequences

- Most chatbot tool calls go directly to apps (lower latency, simpler)
- Aggregator stays focused on composition (its reason for existing)
- 8 direct tools + 1 Aggregator tool = 9 tools total
