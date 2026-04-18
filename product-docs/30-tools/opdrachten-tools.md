# Opdrachten Scanner Tools

**Tool ID:** `rm_opdrachten`
**App:** Ruimtemeesters Opdrachten Scanner (:6300)
**Auth:** Service API key (`rm-opdrachten-service-2026`)
**Status:** Working (E2E verified — 386 archief, 37 genegeerd, 17 interesse)

## Valves

| Name               | Default                    | Description             |
| ------------------ | -------------------------- | ----------------------- |
| opdrachten_api_url | http://opdrachten-api:6300 | Base URL                |
| api_key            |                            | Service API key         |
| timeout            | 30                         | Request timeout seconds |

## Tools

| Method                 | Endpoint                     | Type  | Description                    |
| ---------------------- | ---------------------------- | ----- | ------------------------------ |
| get_inbox              | GET /api/inbox               | READ  | New assignment opportunities   |
| get_pipeline           | GET /api/pipeline            | READ  | Pipeline by stage              |
| get_pipeline_deadlines | GET /api/pipeline/deadlines  | READ  | Items with upcoming deadlines  |
| search_library         | GET /api/library             | READ  | Historical scanned assignments |
| get_stats              | GET /api/stats               | READ  | Pipeline statistics            |
| accept_inbox_item      | POST /api/inbox/:id/accept   | WRITE | Accept item to pipeline        |
| move_pipeline_stage    | POST /api/pipeline/:id/stage | WRITE | Move item between stages       |

## Pipeline Stages

interesse → offerte → gegund → actief → afgerond
→ afgewezen
→ genegeerd
