# Port 5176 Conflict — Workspace vs Sales Viewer Frontend

**Date:** 2026-04-03
**Severity:** medium
**Service:** Riens-Sales-Viewer (Frontend), Ruimtemeesters-Workspace
**Phase found:** 1

## Description

Both the Ruimtemeesters-Workspace dev server (Vite) and the Sales Viewer frontend (Docker/Nginx) bind to host port 5176. When both are running, the second one to start fails.

## Repro steps

1. Start Workspace: `cd Ruimtemeesters-Workspace && pnpm dev` (binds 5176)
2. Start Sales Viewer frontend: `docker compose up -d frontend` (tries to bind 5176, fails)

## Expected

Both services can run simultaneously.

## Actual

```
Error: failed to bind host port 0.0.0.0:5176/tcp: address already in use
```

## Notes

Fix: remap one of them. Workspace could use 5177, or the Sales Viewer frontend could use a different port. The Sales Viewer frontend port is configurable via `FRONTEND_PORT` or similar in docker-compose.yml.

Non-critical because the Sales Viewer API (port 3001) is what the MCP server needs — the frontend is for direct browser access only.
