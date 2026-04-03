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
