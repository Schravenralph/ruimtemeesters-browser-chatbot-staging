# TSA Database Empty — No Tables

**Date:** 2026-04-03
**Severity:** high
**Service:** Ruimtemeesters-TSA
**Phase found:** 3

## Description

The TSA engine's PostgreSQL database (dashboarding) has no tables. API calls return 500 with `relation "dim_gemeente" does not exist`.

## Repro steps

1. `curl -H 'X-API-Key: rm-tsa-service-2026' http://localhost:8100/api/v1/gemeenten`
2. Returns: "Internal Server Error"
3. Logs: `psycopg2.errors.UndefinedTable: relation "dim_gemeente" does not exist`

## Expected

TSA API returns list of gemeenten from dim_gemeente table.

## Actual

500 error — database is empty, needs migrations and data seeding.

## Notes

The TSA database likely needs an initial migration or data import from the Dashboarding service (they share the DB name "dashboarding"). Check if Dashboarding's migration/seed scripts create the tables TSA depends on.

---

## Resolution

**Status:** RESOLVED, verified 2026-04-17.

### Root cause clarification

Filed as "TSA database empty — no migrations". More accurate: TSA and Dashboarding share the same Postgres database (`dashboarding`, currently container `dashboarding-postgres`), and the schema (including `dim_gemeente`) is **owned by Dashboarding's migration suite**, not TSA. When TSA was originally pointed at a fresh/empty DB, all its `SELECT ... FROM dim_gemeente` queries 500'd. The "missing migrations" lived in `Ruimtemeesters-Dashboarding/src/server/db/migrations/001_initial.sql`, which had to run before TSA could function.

### How it got fixed

Two convergent changes:

1. **Dashboarding ran its migrations** on the shared `dashboarding` DB. Current state (live probe):

   ```bash
   $ docker exec dashboarding-postgres psql -U postgres -d dashboarding -tAc \
       "SELECT COUNT(*) FROM _migrations;"
   13
   ```

   All 13 migrations applied (latest `013_sustainability_tables.sql` on 2026-03-26).

2. **TSA was rewired to the shared network** — `Ruimtemeesters-TSA@9c15339` ("refactor: use ruimtemeesters-shared network, drop local postgres") switched TSA from its own postgres to the Dashboarding-owned one. Current `.env`:
   ```
   DB_HOST=dashboarding-postgres
   DB_PORT=5432
   DB_NAME=dashboarding
   ```
   (See also the companion issue `2026-04-03-tsa-db-config-localhost-vs-docker.md`.)

### Verification (live, 2026-04-17)

```bash
$ docker exec dashboarding-postgres psql -U postgres -d dashboarding -tAc \
    "SELECT COUNT(*) FROM dim_gemeente;"
836

$ curl -s -o /tmp/tsa.json -w "HTTP %{http_code}\n" -m 5 \
    "http://localhost:8100/api/v1/gemeenten" \
    -H "X-API-Key: $TSA_API_KEY"
HTTP 200
```

Response contains real gemeente data (`GM0001` Adorp, `GM0003` Appingedam, …).

### Ownership note for future migration work

Dashboarding owns the canonical schema. TSA should not create its own `dim_*` tables or attempt its own migrations against the `dashboarding` DB — doing so risks conflicts. If TSA needs TSA-specific tables (e.g. forecast caches), they should live in a separate schema (`tsa.forecast_runs`) or a separate DB entirely. Platform ADR material if the pattern expands.
