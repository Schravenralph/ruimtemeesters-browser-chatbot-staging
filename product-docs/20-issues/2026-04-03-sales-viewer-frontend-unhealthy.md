# Sales Viewer Frontend Unhealthy

**Date:** 2026-04-03
**Severity:** low
**Service:** Riens-Sales-Viewer (Frontend)
**Phase found:** 1

## Description

Sales Viewer frontend (`sales-viewer-frontend`) Nginx is running (workers started), but container reports unhealthy.

## Repro steps

1. `docker ps | grep sales-viewer-frontend` → unhealthy
2. `docker logs sales-viewer-frontend --tail 20` → Nginx workers running normally

## Expected

Frontend serves the SPA and passes health checks.

## Actual

Unhealthy status. Likely the health check proxies to the API backend which returns 503 (see companion issue `2026-04-03-sales-viewer-api-503-health-check.md`).

## Notes

This is likely a cascading issue. Fix the API health check first, then the frontend should recover.
