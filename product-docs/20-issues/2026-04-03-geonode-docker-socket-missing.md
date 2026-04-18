# GeoNode Unhealthy — Docker Socket Not Mounted

**Date:** 2026-04-03
**Severity:** medium
**Service:** Ruimtemeesters-Geoportaal (GeoNode)
**Phase found:** 1

## Description

GeoNode container (`geoportaal-geonode`) is unhealthy because it tries to access the Docker socket (`/var/run/docker.sock`) from inside the container, but the socket is not mounted as a volume.

## Repro steps

1. `docker logs geoportaal-geonode --tail 30`
2. Observe: `FileNotFoundError(2, 'No such file or directory')` when trying to connect to Docker socket

## Expected

GeoNode starts and serves map/WMS endpoints.

## Actual

Core GeoNode functionality may still work, but internal tasks that need Docker access fail, causing the health check to fail.

## Notes

Fix options:

1. Mount Docker socket: add `- /var/run/docker.sock:/var/run/docker.sock` to GeoNode's volumes in docker-compose.yml (security implication: gives container access to host Docker)
2. Disable the Docker-dependent task in GeoNode config
3. If GeoNode is not critical for the current test round, mark as known issue and skip

---

## Resolution

**Status:** DEFERRED as known-issue 2026-04-17. GeoNode is optional for the Geoportaal backend, which now correctly treats `geonode: disconnected` as non-fatal (see `Ruimtemeesters-Geoportaal/src/server/controllers/health.controller.ts:27` and the healthcheck latency fix in `Ruimtemeesters-Geoportaal/pull/1069`).

### Fresh diagnosis (2026-04-17)

Container still `Up 9 days (unhealthy)`. The actual blocker is NOT that GeoNode is unreachable per se — the `uwsgi` worker never starts. Inspection shows PID 1 is the entrypoint script, PID 41 is a stuck `/usr/local/bin/invoke update` (running since Apr 8). That `invoke update` task calls `client.containers.list(...)` — Docker socket access — and the socket isn't mounted. The task loops/retries silently, so the entrypoint never advances to `uwsgi`, and nothing listens on port 8000 inside the container. Docker healthcheck (`curl -f http://localhost:8000/api/v2/health/`) → "Connection refused".

Relevant inside-container evidence:

```
docker exec geoportaal-geonode ss -lnt
# Only memcached (127.0.0.1:11211) — no uwsgi on :8000
docker logs ... | grep tasks.py:325
# _container_exposed_port → client.containers.list(...)
#   → FileNotFoundError: /var/run/docker.sock
```

### Why deferred

1. **Upstream image issue**: `geonode/geonode:4.4.1` (line `docker-compose.yml:144`) ships an entrypoint that depends on Docker socket access. Patching it means either forking the image or overriding the ENTRYPOINT+command, both invasive.
2. **Not blocking anything critical**: `geonode: disconnected` is accepted by the Geoportaal backend's health aggregator. No MCP tool currently requires GeoNode — the Ruimtelijk Adviseur assistant works via direct backend endpoints.
3. **Security trade-off**: the simplest fix (mount `/var/run/docker.sock` into the container) grants the container full Docker-daemon control — a known container-escape vector. Not acceptable without a dedicated threat-model pass.

### Follow-up options (when/if GeoNode matters)

| Option                                                                                                                          | Effort | Risk                    |
| ------------------------------------------------------------------------------------------------------------------------------- | ------ | ----------------------- |
| A. Mount `/var/run/docker.sock` read-only                                                                                       | low    | high (container escape) |
| B. Switch to GeoServer standalone (no GeoNode wrapper) — already bundled inside the same image at `/geoserver/`                 | medium | medium                  |
| C. Override entrypoint to skip `invoke update` (e.g. `entrypoint: ["/usr/src/app/entrypoint-no-update.sh"]` mounted via volume) | medium | low                     |
| D. Fork the image with a no-Docker entrypoint patch                                                                             | high   | low                     |

If WMS/WMTS becomes load-bearing for the Ruimtelijk Adviseur, start with option **B** — GeoServer is the actual tile server and doesn't need Docker socket access.

Closing as "deferred". Reopen with fresh evidence if GeoNode comes into the critical path.
