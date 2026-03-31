"""
title: Ruimtemeesters Dashboarding
description: Query demographic dashboard data, CBS statistics, and population trends from the Ruimtemeesters Dashboarding platform.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        dashboarding_api_url: str = Field(
            default="http://dashboarding-api:3003",
            description="Base URL of the Dashboarding API",
        )
        timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def get_dashboard_data(
        self,
        query: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Get demographic dashboard data (Primos population/housing projections, CBS data).

        :param query: Optional filter or search query for specific data
        :return: Dashboard data with population projections and statistics
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            params = {}
            if query:
                params["q"] = query
            resp = await client.get(
                f"{self.valves.dashboarding_api_url}/api/data",
                params=params,
            )
            resp.raise_for_status()
            return resp.text

    async def get_statistics(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get summary statistics from the dashboarding platform (population counts, growth rates, key indicators).

        :return: Summary statistics across all tracked municipalities
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.dashboarding_api_url}/api/stats",
            )
            resp.raise_for_status()
            return resp.text

    async def get_trends(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get demographic trend data — population growth, housing development, and other time series trends.

        :return: Trend data with time series for key demographic indicators
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.dashboarding_api_url}/api/trends",
            )
            resp.raise_for_status()
            return resp.text

    async def search_dashboard(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search across all dashboard data for specific demographic information.

        :param query: Search text, e.g. 'bevolkingsgroei Utrecht' or 'woningbouw Randstad'
        :return: Matching dashboard entries with relevant data
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.dashboarding_api_url}/api/search",
                params={"q": query},
            )
            resp.raise_for_status()
            return resp.text
