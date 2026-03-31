"""
title: Ruimtemeesters Geoportaal
description: Query spatial rules, air quality, weather data, building information, and search spatial documents from the Ruimtemeesters Geoportaal.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        geoportaal_api_url: str = Field(
            default="http://geoportaal-api:3000",
            description="Base URL of the Geoportaal API",
        )
        timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def query_spatial_rules(
        self,
        query: str = "",
        rule_id: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Look up spatial planning rules (omgevingsregels) that apply to a location or policy area.

        :param query: Search text for rules, e.g. 'bouwhoogte centrum Amsterdam'
        :param rule_id: Optional specific rule ID to retrieve
        :return: List of applicable rules with descriptions and spatial scope
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            if rule_id:
                resp = await client.get(
                    f"{self.valves.geoportaal_api_url}/v1/rules/{rule_id}",
                )
            else:
                resp = await client.get(
                    f"{self.valves.geoportaal_api_url}/v1/rules",
                    params={"q": query} if query else {},
                )
            resp.raise_for_status()
            return resp.text

    async def get_air_quality(
        self,
        location: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Get air quality (luchtkwaliteit) data for a location in the Netherlands.

        :param location: Municipality name or location description
        :return: Air quality measurements including NO2, PM10, PM2.5
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.geoportaal_api_url}/v1/air-quality",
                params={"location": location} if location else {},
            )
            resp.raise_for_status()
            return resp.text

    async def get_weather(
        self,
        location: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Get current weather data for a location in the Netherlands.

        :param location: Municipality name or location description
        :return: Weather data including temperature, wind, precipitation
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.geoportaal_api_url}/v1/weather",
                params={"location": location} if location else {},
            )
            resp.raise_for_status()
            return resp.text

    async def get_building_data(
        self,
        location: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Get 3D building data (3DBAG) for a location, including building heights and categories.

        :param location: Address or location description
        :return: Building data with geometry, height, and categorization
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.geoportaal_api_url}/v1/building",
                params={"location": location} if location else {},
            )
            resp.raise_for_status()
            return resp.text

    async def search_documents(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search spatial documents and policy maps in the Geoportaal.

        :param query: Search text for documents
        :return: Matching documents with spatial references
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.geoportaal_api_url}/search",
                params={"q": query},
            )
            resp.raise_for_status()
            return resp.text

    async def search_pdok(
        self,
        query: str,
        __user__: dict = {},
    ) -> str:
        """
        Search the PDOK (Kadaster) national geo-datasets for Dutch spatial data.

        :param query: Search text for PDOK datasets
        :return: Matching PDOK datasets and layers
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.geoportaal_api_url}/v1/pdok/search",
                params={"q": query},
            )
            resp.raise_for_status()
            return resp.text
