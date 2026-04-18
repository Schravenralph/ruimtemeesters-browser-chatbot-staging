# Aggregator Tools

**Tool ID:** `rm_aggregator`
**App:** Ruimtemeesters Aggregator (:6000)
**Auth:** API key (`aggregator-dev-key-2026`)
**Status:** Working (E2E verified — Amsterdam 52 docs, 253 search results, 56 KG nodes)

## Valves

| Name               | Default               | Description                |
| ------------------ | --------------------- | -------------------------- |
| aggregator_api_url | http://localhost:6000 | Base URL                   |
| aggregator_api_key |                       | API key (X-API-Key header) |
| timeout            | 30                    | Request timeout seconds    |

## Tools

### Cross-App Context (Databank + Geoportaal combined)

| Method                | Endpoint                           | Type | Description                          |
| --------------------- | ---------------------------------- | ---- | ------------------------------------ |
| context_at_coordinate | GET /v1/context/at                 | READ | Docs + rules at a coordinate         |
| context_municipality  | GET /v1/context/municipality/:code | READ | Municipality overview (docs + rules) |

### Documents (Databank via direct DB)

| Method               | Endpoint                      | Type | Description                       |
| -------------------- | ----------------------------- | ---- | --------------------------------- |
| search_documents     | POST /v1/documents/search     | READ | Full-text policy doc search       |
| get_document_summary | GET /v1/documents/:id/summary | READ | Document summary (first 3 chunks) |

### Spatial (Geoportaal via direct DB)

| Method                 | Endpoint               | Type | Description                       |
| ---------------------- | ---------------------- | ---- | --------------------------------- |
| spatial_rules_at_point | GET /v1/spatial/regels | READ | DSO rules at a coordinate         |
| solar_potential        | GET /v1/spatial/solar  | READ | Solar energy potential in an area |

### Knowledge Graph (Neo4j)

| Method                 | Endpoint              | Type | Description               |
| ---------------------- | --------------------- | ---- | ------------------------- |
| search_knowledge_graph | GET /v1/kg/entities   | READ | Entity name search        |
| get_entity_relations   | GET /v1/kg/entity/:id | READ | Entity with relationships |
| traverse_graph         | POST /v1/kg/traverse  | READ | Multi-hop graph traversal |
| graph_stats            | GET /v1/kg/stats      | READ | Node/relationship counts  |

## Notes

- The Aggregator connects directly to databases (PostgreSQL + Neo4j), bypassing app API auth
- This is the most reliable tool — covers Databank + Geoportaal queries without auth issues
- The first E2E verified tool call: LLM asked about Amsterdam → Aggregator returned 52 real policy documents
