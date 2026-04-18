# TSA Tools

**Tool ID:** `rm_tsa`
**App:** Ruimtemeesters TSA Engine (:8100)
**Auth:** API key (`rm-tsa-service-2026`)
**Status:** Working (E2E verified — 7 models available)

## Valves

| Name        | Default             | Description                          |
| ----------- | ------------------- | ------------------------------------ |
| tsa_api_url | http://tsa-api:8100 | Base URL                             |
| tsa_api_key |                     | API key (X-API-Key header)           |
| timeout     | 120                 | Request timeout (forecasts are slow) |

## Tools

| Method                  | Endpoint                          | Type  | Description                                  |
| ----------------------- | --------------------------------- | ----- | -------------------------------------------- |
| run_population_forecast | POST /api/v1/forecast/bevolking   | WRITE | ML ensemble forecast (Prophet, SARIMA, etc.) |
| get_forecast_results    | GET /api/v1/forecast/:geo_code    | READ  | Cached forecast results                      |
| run_backtest            | POST /api/v1/backtest/bevolking   | WRITE | Walk-forward accuracy validation             |
| get_diagnostics         | GET /api/v1/diagnostics/:geo_code | READ  | Model performance and data quality           |
| list_gemeenten          | GET /api/v1/gemeenten             | READ  | All Dutch municipalities with CBS codes      |
| get_model_status        | GET /api/v1/models/status         | READ  | Available models and last run                |

## Notes

- Forecasts can take 30-120 seconds on CPU (no GPU on server)
- geo_code format: GM0363 (Amsterdam), GM0344 (Utrecht)
- Also available at https://tsa.datameesters.nl
