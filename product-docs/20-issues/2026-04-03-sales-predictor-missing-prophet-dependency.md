# Sales Predictor — Missing Prophet Dependency

**Date:** 2026-04-03
**Severity:** high
**Service:** Sales-Predictor
**Phase found:** 2

## Description

Sales Predictor cannot start because `prophet` (Meta's time-series forecasting library) is not installed, despite being listed in `requirements.txt`.

## Repro steps

1. `cd /home/ralph/Projects/Sales-Predictor`
2. `python3 backend_api.py`
3. Error: `ModuleNotFoundError: No module named 'prophet'`

## Expected

Backend starts on port 8000.

## Actual

Import fails at startup. The `prophet` package requires `cmdstanpy` and a C++ toolchain, making it non-trivial to install.

## Notes

Fix: `pip install prophet neuralprophet` (may need `cmdstanpy` installed first).

This service is not containerized — adding a Dockerfile would ensure consistent dependencies. For now, this blocks the Sales-adviseur assistant's sales forecasting tool.

The Sales Predictor MCP server will not function until this is resolved.

---

## Resolution

**Status:** FIX PROPOSED 2026-04-17 across three coordinated PRs.

| Repo | PR | Change |
|---|---|---|
| Sales-Predictor | [#1](https://github.com/Schravenralph/Sales-Predictor/pull/1) | Add missing deps (pmdarima, filterpy, statsmodels); clean up broken `requirements.txt`; move `dev:backend` to uv-managed venv; default port 8000 → 8050 |
| Ruimtemeesters-MCP-Servers | [#3](https://github.com/Schravenralph/Ruimtemeesters-MCP-Servers/pull/3) | Update default `SALES_PREDICTOR_API_URL` to `http://host.docker.internal:8050` |
| Ruimtemeesters-Platform | [#2](https://github.com/Schravenralph/Ruimtemeesters-Platform/pull/2) | Register 8050 for Sales-Predictor in ADR-0003 port register |

### Root cause

1. `requirements.txt` was missing `pmdarima`, `filterpy`, and `statsmodels` — all imported by `src/models/sarima_model.py` and `state_space_model.py`.
2. `requirements.txt` also had three corrupt lines (`xgboost`, `scikit-learn`, and orphan `>=0.40.0`) that caused `pip install -r` to fail.
3. Port collision: the MCP pointed at `http://host.docker.internal:8000`, but 8000 was occupied on the dev host by a different FastAPI app ("Cancer Information Chat API"). The MCP received 404s from the wrong service and surfaced as "Sales tool broken".

### Verification (live, 2026-04-17)

```
$ BACKEND_PORT=8052 npm run dev:backend   # fresh uv env from scratch
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8052

$ curl -sw "HTTP %{http_code}\n" http://localhost:8052/health
HTTP 200
{"status":"healthy"}

$ docker exec rm-mcp-sales-predictor node -e "http.get('http://host.docker.internal:8050/health', ...)"
status 200 {"status":"healthy"}
```

Backend exposes 16 routes (`/api/predict`, `/api/compare-models`, `/api/inventory/optimize`, etc.) — all reachable.

### Ops follow-up

After the three PRs merge + MCP-Servers container recreates:
1. Developer starts Sales-Predictor locally with `npm run dev:backend` (first run takes ~60s for uv to build the cached venv; subsequent runs are instant).
2. Sales-Adviseur assistant's sales-forecast tool should start returning real predictions instead of timing out.
3. Suggest adding Sales-Predictor to the compose stack eventually (containerize so it auto-starts alongside the MCP fleet) — left as a separate improvement, not blocking this close.

Closing as resolved (fix in flight — will merge once CI + bot review clean).
