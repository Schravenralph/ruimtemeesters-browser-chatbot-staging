# Riens Sales Viewer Tools

**Tool ID:** `rm_riens`
**App:** Riens Sales Viewer (:3001)
**Auth:** Service API key (`rm-riens-service-2026`)
**Status:** Working (API responds, service user gets empty data — needs user context fix)

## Valves

| Name          | Default               | Description             |
| ------------- | --------------------- | ----------------------- |
| riens_api_url | http://riens-api:3001 | Base URL                |
| api_key       |                       | Service API key         |
| timeout       | 30                    | Request timeout seconds |

## Tools

| Method              | Endpoint                      | Type  | Description                             |
| ------------------- | ----------------------------- | ----- | --------------------------------------- |
| get_gemeente_status | GET /api/municipalities       | READ  | All municipalities with contract status |
| update_gemeente     | PUT /api/municipalities/:name | WRITE | Update municipality status or notes     |

## Notes

- Service API key auth works but returns empty data for the service user
- The mock auth (from host) returns full data — the service user role needs municipality assignment
- Fix: add municipality access for the service user in Riens
