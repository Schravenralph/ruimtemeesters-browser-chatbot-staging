# Databank Tools

**Tool ID:** `rm_databank`
**App:** Ruimtemeesters Databank (:4000)
**Auth:** Service API key (`rm-databank-service-2026`)
**Status:** Blocked (search route uses internal auth) — use Aggregator instead

## Valves

| Name             | Default                  | Description                 |
| ---------------- | ------------------------ | --------------------------- |
| databank_api_url | http://databank-api:4000 | Base URL                    |
| api_key          |                          | Service API key (X-API-Key) |
| timeout          | 30                       | Request timeout seconds     |

## Tools

| Method                   | Endpoint                         | Type  | Description                                            |
| ------------------------ | -------------------------------- | ----- | ------------------------------------------------------ |
| search_beleidsdocumenten | GET /api/search                  | READ  | Hybrid keyword+semantic search across policy documents |
| get_knowledge_graph      | GET /api/knowledge-graph         | READ  | Traverse Neo4j relationships                           |
| get_document             | GET /api/canonical-documents/:id | READ  | Full document details                                  |
| list_queries             | GET /api/queries                 | READ  | User's beleidsscan queries                             |
| create_query             | POST /api/queries                | WRITE | Start a new beleidsscan                                |

## Notes

- The search route applies auth internally via `createSearchRouter` — our SERVICE_API_KEY bypass in `authMiddleware.ts` doesn't reach it
- Use the Aggregator tool (`rm_aggregator`) for document search — it has direct DB access and works fully
