# Dashboarding Tools

**Tool ID:** `rm_dashboarding`
**App:** Ruimtemeesters Dashboarding (:5022)
**Auth:** JWT (admin@ruimtemeesters.nl / admin12345) — service key not yet added
**Status:** Working (10 themes, stats/overview available)

## Valves

| Name                 | Default                      | Description             |
| -------------------- | ---------------------------- | ----------------------- |
| dashboarding_api_url | http://dashboarding-api:5022 | Base URL                |
| timeout              | 30                           | Request timeout seconds |

## Tools

| Method             | Endpoint                 | Type | Description                          |
| ------------------ | ------------------------ | ---- | ------------------------------------ |
| get_dashboard_data | GET /api/data/query      | READ | Primos/CBS demographic data          |
| get_statistics     | GET /api/stats/overview  | READ | Summary statistics                   |
| get_trends         | GET /api/trends/overview | READ | Population growth and housing trends |
| search_dashboard   | GET /api/search          | READ | Search across all dashboard data     |

## Notes

- Most endpoints require JWT auth — chatbot currently uses unauthenticated access
- /api/themes works without auth (10 themes)
- Future: add SERVICE_API_KEY bypass like other apps
