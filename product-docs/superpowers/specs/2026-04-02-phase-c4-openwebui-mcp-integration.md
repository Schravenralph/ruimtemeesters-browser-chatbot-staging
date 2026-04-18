# Phase C4: OpenWebUI MCP Integration — Design Spec

**Date:** 2026-04-02
**Status:** Implemented
**Depends on:** Phase C1-C3 (MCP servers, implemented), MCP auth & corrections (implemented)

---

## Context

The MCP servers monorepo (`Ruimtemeesters-MCP-Servers`) has 8 servers with 48 tools, all supporting HTTP transport mode. OpenWebUI v0.8.12 has native MCP client support. Phase A Python tools (`rm-tools/*.py`) in the OpenWebUI fork do the same thing as the MCP servers — wrap backend REST APIs. This spec replaces them.

## Goal

1. Deploy all 8 MCP servers as Docker containers in HTTP mode
2. Connect OpenWebUI to them via its native MCP Tool Server configuration
3. Update assistant tool assignments to reference MCP server tool IDs
4. Remove the Phase A Python tools from the OpenWebUI fork

## Non-Goals

- Changing MCP server tool logic or adding new tools
- Modifying OpenWebUI's MCP client code
- SSE transport (HTTP Streamable is what OpenWebUI uses)
- Phase C5 (Claude Code/Cursor config — already working via stdio)

---

## 1. Docker Deployment

### Dockerfile (MCP repo root)

A single shared Dockerfile for all 8 servers:

```dockerfile
FROM node:22-slim AS base
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
COPY packages/ packages/
RUN pnpm install --frozen-lockfile

ARG PACKAGE
ENV PACKAGE=${PACKAGE}
ENV MCP_TRANSPORT=http
CMD pnpm exec tsx packages/${PACKAGE}/src/server.ts --http
```

Note: `CMD` uses shell form (no JSON array) so `${PACKAGE}` is expanded at runtime. `ENV PACKAGE=${PACKAGE}` bakes the build arg into the image. Each service sets `PACKAGE` via build arg in docker-compose.

### docker-compose.yaml (MCP repo)

8 services, one per MCP server. All on a shared `rm-network`.

| Service             | Container              | Port | Package         | API URL Env Var           |
| ------------------- | ---------------------- | ---- | --------------- | ------------------------- |
| mcp-databank        | rm-mcp-databank        | 3101 | databank        | `DATABANK_API_URL`        |
| mcp-geoportaal      | rm-mcp-geoportaal      | 3102 | geoportaal      | `GEOPORTAAL_API_URL`      |
| mcp-tsa             | rm-mcp-tsa             | 3103 | tsa             | `TSA_API_URL`             |
| mcp-dashboarding    | rm-mcp-dashboarding    | 3104 | dashboarding    | `DASHBOARDING_API_URL`    |
| mcp-riens           | rm-mcp-riens           | 3105 | riens           | `RIENS_API_URL`           |
| mcp-sales-predictor | rm-mcp-sales-predictor | 3106 | sales-predictor | `SALES_PREDICTOR_API_URL` |
| mcp-opdrachten      | rm-mcp-opdrachten      | 3107 | opdrachten      | `OPDRACHTEN_API_URL`      |
| mcp-aggregator      | rm-mcp-aggregator      | 3108 | aggregator      | `AGGREGATOR_API_URL`      |

Each service passes its `--port` flag matching its assigned port, plus API URL and API key env vars from the host `.env` file.

Network: `rm-network` defined as an external Docker network. Created once with `docker network create rm-network`. Both the MCP compose and the OpenWebUI compose join it.

### Health checks

Each MCP server already exposes `GET /health` returning `{"status":"ok","transport":"http"}`. Docker Compose health checks use this endpoint.

---

## 2. OpenWebUI Tool Server Configuration

### Connection format

OpenWebUI's `TOOL_SERVER_CONNECTIONS` env var accepts a JSON array. Each MCP server is one entry:

```json
{
	"type": "mcp",
	"url": "http://rm-mcp-databank:3101/mcp",
	"auth_type": "none",
	"headers": {
		"X-API-Key": "your-databank-api-key-here"
	},
	"info": {
		"id": "rm-databank",
		"name": "Ruimtemeesters Databank",
		"description": "Policy documents, knowledge graph, beleidsscan"
	},
	"config": {
		"enable": true
	}
}
```

**Auth approach:** `auth_type` is `none` (no auto-generated Authorization header). The `X-API-Key` header is set via the custom `headers` field. OpenWebUI merges custom headers into every request to the MCP server. This matches the pattern all backend apps already use.

### All 8 connections

| Server ID            | URL                                      | Name                              |
| -------------------- | ---------------------------------------- | --------------------------------- |
| `rm-databank`        | `http://rm-mcp-databank:3101/mcp`        | Ruimtemeesters Databank           |
| `rm-geoportaal`      | `http://rm-mcp-geoportaal:3102/mcp`      | Ruimtemeesters Geoportaal         |
| `rm-tsa`             | `http://rm-mcp-tsa:3103/mcp`             | Ruimtemeesters TSA                |
| `rm-dashboarding`    | `http://rm-mcp-dashboarding:3104/mcp`    | Ruimtemeesters Dashboarding       |
| `rm-riens`           | `http://rm-mcp-riens:3105/mcp`           | Ruimtemeesters Riens Sales Viewer |
| `rm-sales-predictor` | `http://rm-mcp-sales-predictor:3106/mcp` | Ruimtemeesters Sales Predictor    |
| `rm-opdrachten`      | `http://rm-mcp-opdrachten:3107/mcp`      | Ruimtemeesters Opdrachten Scanner |
| `rm-aggregator`      | `http://rm-mcp-aggregator:3108/mcp`      | Ruimtemeesters Aggregator         |

### Where to configure

Add `TOOL_SERVER_CONNECTIONS` as an environment variable in OpenWebUI's `docker-compose.yaml`. The value is a JSON-encoded array of the 8 connection objects above.

---

## 3. Assistant Tool Assignment Updates

### Current tool ID format (Phase A)

Assistants reference local Python tools by their tool ID:

```
toolIds: ["rm_databank", "rm_geoportaal", "rm_aggregator"]
```

### New tool ID format (MCP)

MCP Tool Server tools use the format `server:mcp:{server_id}`:

```
toolIds: ["server:mcp:rm-databank", "server:mcp:rm-geoportaal", "server:mcp:rm-aggregator"]
```

### Assistant mapping

| Assistant                | Current toolIds                                   | New toolIds                                                                        |
| ------------------------ | ------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Beleidsadviseur          | `rm_databank`, `rm_geoportaal`, `rm_aggregator`   | `server:mcp:rm-databank`, `server:mcp:rm-geoportaal`, `server:mcp:rm-aggregator`   |
| Demografie Analist       | `rm_dashboarding`, `rm_tsa`                       | `server:mcp:rm-dashboarding`, `server:mcp:rm-tsa`                                  |
| Ruimtelijk Adviseur      | `rm_geoportaal`, `rm_databank`, `rm_aggregator`   | `server:mcp:rm-geoportaal`, `server:mcp:rm-databank`, `server:mcp:rm-aggregator`   |
| Sales Adviseur           | `rm_riens`, `rm_sales_predictor`, `rm_opdrachten` | `server:mcp:rm-riens`, `server:mcp:rm-sales-predictor`, `server:mcp:rm-opdrachten` |
| Ruimtemeesters Assistent | all 8 tools                                       | all 8 `server:mcp:*` IDs                                                           |

The update is done in `rm-tools/register_assistants.py` (which seeds the database) and then re-run the registration script.

---

## 4. Phase A Tool Removal

### Files to delete from OpenWebUI fork

```
rm-tools/databank.py
rm-tools/geoportaal.py
rm-tools/tsa.py
rm-tools/dashboarding.py
rm-tools/riens.py
rm-tools/sales_predictor.py
rm-tools/opdrachten.py
rm-tools/aggregator.py
rm-tools/register_tools.py
```

### Files to keep and modify

- `rm-tools/register_assistants.py` — Update toolIds to MCP format, keep the script for re-seeding assistants

### Database cleanup

The old Python tools are stored in OpenWebUI's `tool` table. After connecting MCP servers and verifying they work, remove the old tool entries either:

- Via the Admin UI (Settings → Tools → delete each)
- Via the registration script (add a cleanup step)

---

## 5. Migration Order

1. Create Docker network: `docker network create rm-network`
2. Add Dockerfile and docker-compose.yaml to MCP repo
3. Build and start MCP containers: `docker compose up -d`
4. Verify health: `curl http://localhost:3101/health` (for each server)
5. Add `TOOL_SERVER_CONNECTIONS` to OpenWebUI's docker-compose.yaml
6. Join OpenWebUI to `rm-network`
7. Restart OpenWebUI
8. Verify MCP tools appear in OpenWebUI Admin → Tool Servers
9. Update `register_assistants.py` with new tool IDs
10. Re-run assistant registration
11. Test each assistant end-to-end
12. Delete `rm-tools/*.py` Python tool files
13. Remove old tool entries from OpenWebUI database
14. Commit and push both repos

---

## 6. Files Changed Summary

### MCP Servers repo (`Ruimtemeesters-MCP-Servers`)

| File                  | Change                                           |
| --------------------- | ------------------------------------------------ |
| `Dockerfile`          | New — shared multi-stage Dockerfile              |
| `docker-compose.yaml` | New — 8 MCP server services                      |
| `.env.example`        | Add port assignments (already has API URLs/keys) |

### OpenWebUI fork (`ruimtemeesters-openwebui`)

| File                              | Change                                                   |
| --------------------------------- | -------------------------------------------------------- |
| `docker-compose.yaml`             | Add `TOOL_SERVER_CONNECTIONS` env var, join `rm-network` |
| `rm-tools/register_assistants.py` | Update toolIds to `server:mcp:*` format                  |
| `rm-tools/databank.py`            | Delete                                                   |
| `rm-tools/geoportaal.py`          | Delete                                                   |
| `rm-tools/tsa.py`                 | Delete                                                   |
| `rm-tools/dashboarding.py`        | Delete                                                   |
| `rm-tools/riens.py`               | Delete                                                   |
| `rm-tools/sales_predictor.py`     | Delete                                                   |
| `rm-tools/opdrachten.py`          | Delete                                                   |
| `rm-tools/aggregator.py`          | Delete                                                   |
| `rm-tools/register_tools.py`      | Delete                                                   |
