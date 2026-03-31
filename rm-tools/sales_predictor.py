"""
title: Ruimtemeesters Sales Predictor
description: Run sales forecasts using ML models (Prophet, SARIMA, Holt-Winters, ensemble) and compare model performance for HorecA sector predictions.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        sales_predictor_api_url: str = Field(
            default="http://sales-predictor-api:8001",
            description="Base URL of the Sales Predictor API",
        )
        timeout: int = Field(default=120, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def run_sales_forecast(
        self,
        model_type: str = "prophet",
        target_column: str = "sales",
        test_days: int = 30,
        __user__: dict = {},
    ) -> str:
        """
        Run a sales forecast using the specified ML model.

        :param model_type: Model to use: 'prophet', 'sarima', 'holt_winters', 'state_space', 'xgboost', 'neuralprophet', or 'lstm'
        :param target_column: Column to predict (default 'sales')
        :param test_days: Number of days for test/validation period
        :return: Forecast results with predictions and confidence intervals
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.sales_predictor_api_url}/api/train",
                json={
                    "model_type": model_type,
                    "target_column": target_column,
                    "test_days": test_days,
                },
            )
            resp.raise_for_status()
            return resp.text

    async def get_predictions(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get the latest sales predictions from trained models.

        :return: Predictions with dates, values, and confidence intervals
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.sales_predictor_api_url}/api/predict",
                json={},
            )
            resp.raise_for_status()
            return resp.text

    async def compare_models(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Compare the performance of different forecasting models (MAE, RMSE, MAPE metrics).

        :return: Model comparison with accuracy metrics for each trained model
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.sales_predictor_api_url}/api/comparison",
            )
            resp.raise_for_status()
            return resp.text

    async def list_models(
        self,
        __user__: dict = {},
    ) -> str:
        """
        List available forecasting models and their training status.

        :return: Available models with last training timestamp and metrics
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.sales_predictor_api_url}/api/models",
            )
            resp.raise_for_status()
            return resp.text
