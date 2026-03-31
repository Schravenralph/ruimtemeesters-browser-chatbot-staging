"""
title: Ruimtemeesters Sales Viewer
description: Query municipality contract status, sales data, and geographic sales intelligence from the Riens Sales Viewer.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        riens_api_url: str = Field(
            default="http://riens-api:7707",
            description="Base URL of the Riens Sales Viewer API",
        )
        timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def get_gemeente_status(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get the contract status of all Dutch municipalities — which ones have active contracts with Ruimtemeesters, which are archived, organized by province.

        :return: List of municipalities with contract status (active/archived), province, and service type
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.riens_api_url}/api/municipalities",
            )
            resp.raise_for_status()
            return resp.text

    async def update_gemeente(
        self,
        municipality_name: str,
        status: str = "",
        notes: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Update the status or notes for a municipality in the sales viewer.

        :param municipality_name: Name of the municipality to update
        :param status: New status value (e.g. 'active', 'archived', 'prospect')
        :param notes: Optional notes to add
        :return: Updated municipality record
        """
        body = {}
        if status:
            body["status"] = status
        if notes:
            body["notes"] = notes

        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.put(
                f"{self.valves.riens_api_url}/api/municipalities/{municipality_name}",
                json=body,
            )
            resp.raise_for_status()
            return resp.text
