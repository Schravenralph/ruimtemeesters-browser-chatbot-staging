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
