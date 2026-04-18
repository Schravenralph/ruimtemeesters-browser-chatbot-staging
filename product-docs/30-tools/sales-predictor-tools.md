# Sales Predictor Tools

**Tool ID:** `rm_sales_predictor`
**App:** Sales Predictor (:8000)
**Auth:** None (no auth required)
**Status:** Working (API responds, no trained models yet)

## Valves

| Name                    | Default                         | Description                        |
| ----------------------- | ------------------------------- | ---------------------------------- |
| sales_predictor_api_url | http://sales-predictor-api:8000 | Base URL                           |
| timeout                 | 120                             | Request timeout (training is slow) |

## Tools

| Method             | Endpoint                | Type  | Description                                       |
| ------------------ | ----------------------- | ----- | ------------------------------------------------- |
| run_sales_forecast | POST /api/train         | WRITE | Train model (prophet, sarima, holt_winters, etc.) |
| get_predictions    | POST /api/predict       | READ  | Latest predictions from trained models            |
| compare_models     | GET /api/compare-models | READ  | Model performance comparison (MAE, RMSE, MAPE)    |
| list_models        | GET /api/models/status  | READ  | Available models and training status              |

## Notes

- Requires CSV data upload before training (POST /api/upload-data)
- No models trained yet — list_models returns empty
- Also available at https://salespredictor.datameesters.nl
- Swagger docs at /docs
