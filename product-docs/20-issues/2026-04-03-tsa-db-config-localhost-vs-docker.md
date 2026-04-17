# TSA DB Config — localhost vs Docker Service Name

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-TSA
**Phase found:** 1

## Description

TSA's `.env` had `DB_HOST=localhost` and `DB_PORT=6433`. When running in Docker:
- `localhost` resolves to the TSA container itself, not the Postgres container
- Port 6433 is the Dashboarding DB's host port, not TSA's own DB (which is 6435 on host, 5432 inside Docker)

This caused TSA to report `db_connected: false` with `status: degraded`.

## Fix applied

Changed `.env` to:
```
DB_HOST=postgres    # Docker service name
DB_PORT=5432        # Container port (not host-mapped port)
```

## Notes

This is a common pattern issue across the stack: `.env` files that work for local development (localhost + host port) break inside Docker (need service name + container port). Consider documenting which `.env` values need to change for Docker vs local development.

Also: the `.env` initially pointed at port 6433 (Dashboarding DB) instead of 6435 (TSA's own DB). Even for localhost usage, this was wrong.

---

## Resolution

**Status:** RESOLVED, verified 2026-04-17.

Current `Ruimtemeesters-TSA/.env` now uses Docker service names and internal ports:

```
DB_HOST=dashboarding-postgres
DB_PORT=5432
DB_NAME=dashboarding
# DB_USER / DB_PASSWORD intentionally omitted — see .env for credentials
```

Landed as part of `Ruimtemeesters-TSA@9c15339` ("refactor: use ruimtemeesters-shared network, drop local postgres"), which also drops the per-repo postgres container and connects TSA to the shared `ruimtemeesters-databank-network` where Dashboarding's postgres lives.

### Verification (live, 2026-04-17)

```bash
$ docker ps --format "{{.Names}}\t{{.Status}}" | grep tsa-engine
tsa-engine  Up 3 days (healthy)

$ curl -s http://localhost:8100/health -H "X-API-Key: $TSA_API_KEY"
{"status":"ok","db_connected":true,"status_detail":"healthy"}
```

`db_connected: true`, no more `status: degraded`.

### Related memory

This issue was part of the broader "localhost vs service name" pattern for cross-repo Docker networking. The fix (single shared network + container names in env) is now the conventional pattern across the fleet — worth documenting in a future Platform ADR alongside the port-allocation ADR.

Closing as resolved.
