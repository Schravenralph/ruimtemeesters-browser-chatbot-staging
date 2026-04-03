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
