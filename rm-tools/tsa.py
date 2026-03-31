"""
title: Ruimtemeesters TSA
description: Run demographic time series forecasts, backtests, and diagnostics using the Ruimtemeesters TSA engine (Prophet, SARIMA, Holt-Winters, State-Space, ensemble).
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        tsa_api_url: str = Field(
            default="http://tsa-api:8000",
            description="Base URL of the TSA API",
        )
        tsa_api_key: str = Field(
            default="",
            description="API key for the TSA service",
        )
        timeout: int = Field(default=120, description="Request timeout in seconds (forecasts can be slow)")

    def __init__(self):
        self.valves = self.Valves()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.valves.tsa_api_key:
            h["X-API-Key"] = self.valves.tsa_api_key
        return h

    async def run_population_forecast(
        self,
        geo_code: str,
        __user__: dict = {},
    ) -> str:
        """
        Run a demographic population forecast for a Dutch municipality using ML ensemble models (Prophet, SARIMA, Holt-Winters, State-Space).

        :param geo_code: CBS gemeente code, e.g. 'GM0363' for Amsterdam or 'GM0344' for Utrecht
        :return: Forecast results with predictions, confidence intervals, and model weights
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.tsa_api_url}/api/forecast/bevolking",
                json={"geo_code": geo_code},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text

    async def get_forecast_results(
        self,
        geo_code: str,
        __user__: dict = {},
    ) -> str:
        """
        Get cached forecast results for a municipality (from a previous forecast run).

        :param geo_code: CBS gemeente code, e.g. 'GM0363' for Amsterdam
        :return: Cached forecast data with predictions and confidence intervals
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.tsa_api_url}/api/forecast/{geo_code}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text

    async def run_backtest(
        self,
        geo_code: str,
        __user__: dict = {},
    ) -> str:
        """
        Run a walk-forward backtest to validate forecast accuracy against historical data for a municipality.

        :param geo_code: CBS gemeente code, e.g. 'GM0363' for Amsterdam
        :return: Backtest results with accuracy metrics per model
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.tsa_api_url}/api/backtest/bevolking",
                json={"geo_code": geo_code},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text

    async def get_diagnostics(
        self,
        geo_code: str,
        __user__: dict = {},
    ) -> str:
        """
        Get forecast diagnostics for a municipality — model performance, residuals, and data quality.

        :param geo_code: CBS gemeente code, e.g. 'GM0363'
        :return: Diagnostic report with model metrics and data quality indicators
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.tsa_api_url}/api/diagnostics/{geo_code}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text

    async def list_gemeenten(
        self,
        __user__: dict = {},
    ) -> str:
        """
        List all known Dutch municipalities with their CBS codes and metadata.

        :return: List of municipalities with geo_code, name, and province
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.tsa_api_url}/api/gemeenten",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text

    async def get_model_status(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get status of available forecast models and the latest forecast run.

        :return: Available models and their latest run timestamps
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.tsa_api_url}/api/models/status",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text
