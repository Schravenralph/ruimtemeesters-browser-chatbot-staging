# Geoportaal Tools

**Tool ID:** `rm_geoportaal`
**App:** Ruimtemeesters Geoportaal (:5002)
**Auth:** Service API key (`rm-geoportaal-service-2026`)
**Status:** Partial (bound to 127.0.0.1 — not reachable from Docker)

## Valves

| Name               | Default                        | Description                    |
| ------------------ | ------------------------------ | ------------------------------ |
| geoportaal_api_url | http://geoportaal-api:5002/api | Base URL (include /api prefix) |
| api_key            |                                | Service API key                |
| timeout            | 30                             | Request timeout seconds        |

## Tools

| Method              | Endpoint            | Type | Description                              |
| ------------------- | ------------------- | ---- | ---------------------------------------- |
| query_spatial_rules | GET /v1/rules       | READ | Spatial planning rules (omgevingsregels) |
| get_air_quality     | GET /v1/air-quality | READ | Luchtkwaliteit data                      |
| get_weather         | GET /v1/weather     | READ | Current weather                          |
| get_building_data   | GET /v1/building    | READ | 3D building data (3DBAG)                 |
| search_documents    | GET /search         | READ | Spatial documents and policy maps        |
| search_pdok         | GET /v1/pdok/search | READ | PDOK (Kadaster) national datasets        |

## Notes

- Geoportaal binds to 127.0.0.1 — not reachable from Docker container
- Use the Aggregator for spatial queries that need Geoportaal data
- Fix: change Geoportaal's PORT binding to 0.0.0.0 in its .env or startup
