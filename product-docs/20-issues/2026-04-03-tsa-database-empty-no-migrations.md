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
