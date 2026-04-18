# Phase A3 + A4: Tool Integrations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the chatbot read/write access to all Ruimtemeesters apps via OpenWebUI Tools, plus cross-app Aggregator composition.

**Architecture:** Each app gets one OpenWebUI Tool file (Python class) with methods that call the app's REST API. Tools are stored in `rm-tools/` in the staging repo and registered via OpenWebUI's API. Each tool uses `httpx` for async HTTP calls, forwards the user context, and has configurable Valves for the app URL. Cross-app queries go through the Aggregator.

**Tech Stack:** Python 3.11, httpx, OpenWebUI Tool API, Pydantic (Valves)

**Spec reference:** `docs/superpowers/specs/2026-03-31-browser-chatbot-design.md` — Sections 5, 9 (A3, A4)

---

## File Structure

### New files (in staging repo `/home/ralph/Projects/ruimtemeesters-openwebui/`)

| File                          | Responsibility                                                 |
| ----------------------------- | -------------------------------------------------------------- |
| `rm-tools/databank.py`        | Databank: search beleid, knowledge graph, queries              |
| `rm-tools/geoportaal.py`      | Geoportaal: spatial rules, air quality, weather, building data |
| `rm-tools/dashboarding.py`    | Dashboarding: dashboard data, stats, trends                    |
| `rm-tools/tsa.py`             | TSA: forecasts, backtests, diagnostics, gemeenten              |
| `rm-tools/riens.py`           | Riens Sales Viewer: municipality status, export                |
| `rm-tools/sales_predictor.py` | Sales Predictor: train, predict, compare models                |
| `rm-tools/opdrachten.py`      | Opdrachten Scanner: inbox, pipeline, library, stats            |
| `rm-tools/aggregator.py`      | Aggregator: cross-app composition queries                      |
| `rm-tools/register_tools.py`  | Script to register all tools via OpenWebUI API                 |

---

## Task 1: Create rm-tools directory and shared base

**Files:**

- Create: `rm-tools/README.md`

- [ ] **Step 1: Create the tools directory**

```bash
mkdir -p /home/ralph/Projects/ruimtemeesters-openwebui/rm-tools
```

- [ ] **Step 2: Create README**

````markdown
# Ruimtemeesters AI — OpenWebUI Tools

Custom tools for the Ruimtemeesters chatbot. Each file is a standalone
OpenWebUI Tool that gets registered via the API.

## Registration

```bash
python rm-tools/register_tools.py --url http://localhost:3333 --token <admin-token>
```
````

## Tool Files

| File               | App                | Capabilities                            |
| ------------------ | ------------------ | --------------------------------------- |
| databank.py        | Databank           | Search beleid, knowledge graph, queries |
| geoportaal.py      | Geoportaal         | Spatial rules, air quality, weather     |
| dashboarding.py    | Dashboarding       | Data, stats, trends                     |
| tsa.py             | TSA Engine         | Forecasts, backtests, diagnostics       |
| riens.py           | Riens Sales Viewer | Municipality status                     |
| sales_predictor.py | Sales Predictor    | Train, predict, compare                 |
| opdrachten.py      | Opdrachten Scanner | Inbox, pipeline, library                |
| aggregator.py      | Aggregator         | Cross-app composition queries           |

````

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git checkout -b rm/tool-integrations
git add rm-tools/
git commit -m "chore: create rm-tools directory for OpenWebUI tool files"
````

---

## Task 2: Databank Tool

**Files:**

- Create: `rm-tools/databank.py`

- [ ] **Step 1: Create the Databank tool**

```python
"""
title: Ruimtemeesters Databank
description: Search policy documents, query the knowledge graph, and manage beleidsscan queries in the Ruimtemeesters Databank.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        databank_api_url: str = Field(
            default="http://databank-api:4000",
            description="Base URL of the Databank API",
        )
        timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def search_beleidsdocumenten(
        self,
        query: str,
        location: str = "",
        document_type: str = "",
        limit: int = 10,
        __user__: dict = {},
    ) -> str:
        """
        Search for Dutch policy documents (beleidsstukken) using hybrid keyword and semantic search.

        :param query: Search query in Dutch, e.g. 'luchtkwaliteit' or 'woningbouw Den Haag'
        :param location: Optional municipality or region name to filter by
        :param document_type: Optional document type filter
        :param limit: Maximum number of results (default 10)
        :return: Search results with document titles, summaries, and metadata
        """
        params = {"q": query, "limit": limit}
        if location:
            params["location"] = location
        if document_type:
            params["documentType"] = document_type

        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.databank_api_url}/api/search",
                params=params,
            )
            resp.raise_for_status()
            return resp.text

    async def get_knowledge_graph(
        self,
        entity_id: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Query the Databank knowledge graph to explore relationships between policies, topics, and municipalities.

        :param entity_id: Optional specific entity ID to get with its neighbors. Leave empty for overview.
        :return: Knowledge graph data with entities and relationships
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            if entity_id:
                resp = await client.get(
                    f"{self.valves.databank_api_url}/api/knowledge-graph/entity/{entity_id}",
                )
            else:
                resp = await client.get(
                    f"{self.valves.databank_api_url}/api/knowledge-graph",
                    params={"limit": 50},
                )
            resp.raise_for_status()
            return resp.text

    async def get_document(
        self,
        document_id: str,
        __user__: dict = {},
    ) -> str:
        """
        Get the full details of a specific canonical document from the Databank.

        :param document_id: The document ID to retrieve
        :return: Full document with metadata, content, and related entities
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.databank_api_url}/api/canonical-documents/{document_id}",
            )
            resp.raise_for_status()
            return resp.text

    async def list_queries(
        self,
        __user__: dict = {},
    ) -> str:
        """
        List the user's beleidsscan queries (policy scan searches).

        :return: List of queries with their status and results
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.databank_api_url}/api/queries",
            )
            resp.raise_for_status()
            return resp.text

    async def create_query(
        self,
        search_text: str,
        location: str = "",
        __user__: dict = {},
    ) -> str:
        """
        Start a new beleidsscan query to search for and analyze policy documents.

        :param search_text: The policy topic to search for, e.g. 'luchtkwaliteit maatregelen'
        :param location: Optional municipality or region to scope the search
        :return: Created query with ID and initial status
        """
        body = {"searchText": search_text}
        if location:
            body["location"] = location

        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.databank_api_url}/api/queries",
                json=body,
            )
            resp.raise_for_status()
            return resp.text
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/databank.py
git commit -m "feat: add Databank tool — search beleid, knowledge graph, queries"
```

---

## Task 3: Geoportaal Tool

**Files:**

- Create: `rm-tools/geoportaal.py`

- [ ] **Step 1: Create the Geoportaal tool**

```python
"""
title: Ruimtemeesters Geoportaal
description: Query spatial rules, air quality, weather data, building information, and generate map exports from the Ruimtemeesters Geoportaal.
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
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/geoportaal.py
git commit -m "feat: add Geoportaal tool — spatial rules, air quality, weather, buildings"
```

---

## Task 4: TSA Tool

**Files:**

- Create: `rm-tools/tsa.py`

- [ ] **Step 1: Create the TSA tool**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/tsa.py
git commit -m "feat: add TSA tool — population forecasts, backtests, diagnostics"
```

---

## Task 5: Dashboarding Tool

**Files:**

- Create: `rm-tools/dashboarding.py`

- [ ] **Step 1: Create the Dashboarding tool**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/dashboarding.py
git commit -m "feat: add Dashboarding tool — demographic data, stats, trends"
```

---

## Task 6: Riens Sales Viewer Tool

**Files:**

- Create: `rm-tools/riens.py`

- [ ] **Step 1: Create the Riens tool**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/riens.py
git commit -m "feat: add Riens Sales Viewer tool — gemeente status"
```

---

## Task 7: Sales Predictor Tool

**Files:**

- Create: `rm-tools/sales_predictor.py`

- [ ] **Step 1: Create the Sales Predictor tool**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/sales_predictor.py
git commit -m "feat: add Sales Predictor tool — forecasts, predictions, model comparison"
```

---

## Task 8: Opdrachten Scanner Tool

**Files:**

- Create: `rm-tools/opdrachten.py`

- [ ] **Step 1: Create the Opdrachten Scanner tool**

```python
"""
title: Ruimtemeesters Opdrachten Scanner
description: Search and manage DAS/inhuur assignments from TenderNED and other platforms. View inbox, pipeline, and historical library.
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        opdrachten_api_url: str = Field(
            default="http://opdrachten-api:6300",
            description="Base URL of the Opdrachten Scanner API",
        )
        timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()

    async def get_inbox(
        self,
        limit: int = 20,
        __user__: dict = {},
    ) -> str:
        """
        Get new assignment opportunities waiting in the inbox (not yet triaged).

        :param limit: Maximum number of items to return (default 20, max 100)
        :return: Inbox items with assignment details, platform, buyer, and deadline
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.opdrachten_api_url}/api/inbox",
                params={"limit": min(limit, 100)},
            )
            resp.raise_for_status()
            return resp.text

    async def get_pipeline(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get the current assignment pipeline — items organized by stage (interesse, offerte, gegund, actief, afgerond).

        :return: Pipeline items grouped by stage with details and deadlines
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.opdrachten_api_url}/api/pipeline",
            )
            resp.raise_for_status()
            return resp.text

    async def get_pipeline_deadlines(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get pipeline items with upcoming deadlines.

        :return: Items sorted by deadline date
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.opdrachten_api_url}/api/pipeline/deadlines",
            )
            resp.raise_for_status()
            return resp.text

    async def search_library(
        self,
        query: str = "",
        platform: str = "",
        buyer: str = "",
        service: str = "",
        limit: int = 20,
        __user__: dict = {},
    ) -> str:
        """
        Search the historical library of all scanned assignments with filters.

        :param query: Free text search
        :param platform: Filter by platform (e.g. 'TenderNED')
        :param buyer: Filter by buying organization
        :param service: Filter by service type
        :param limit: Max results (default 20)
        :return: Matching assignments with full details
        """
        params = {"limit": limit}
        if query:
            params["q"] = query
        if platform:
            params["platform"] = platform
        if buyer:
            params["buyer"] = buyer
        if service:
            params["service"] = service

        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.opdrachten_api_url}/api/library",
                params=params,
            )
            resp.raise_for_status()
            return resp.text

    async def get_stats(
        self,
        __user__: dict = {},
    ) -> str:
        """
        Get assignment pipeline statistics — counts per stage, conversion rates, activity summary.

        :return: Statistics overview of the opdrachten pipeline
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.opdrachten_api_url}/api/stats",
            )
            resp.raise_for_status()
            return resp.text

    async def accept_inbox_item(
        self,
        item_id: str,
        __user__: dict = {},
    ) -> str:
        """
        Accept an inbox item and move it to the pipeline (interesse stage).

        :param item_id: ID of the inbox item to accept
        :return: Updated item now in the pipeline
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.opdrachten_api_url}/api/inbox/{item_id}/accept",
            )
            resp.raise_for_status()
            return resp.text

    async def move_pipeline_stage(
        self,
        item_id: str,
        stage: str,
        __user__: dict = {},
    ) -> str:
        """
        Move a pipeline item to a different stage.

        :param item_id: ID of the pipeline item
        :param stage: Target stage: 'interesse', 'offerte', 'gegund', 'actief', 'afgerond', 'afgewezen', or 'genegeerd'
        :return: Updated pipeline item
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.post(
                f"{self.valves.opdrachten_api_url}/api/pipeline/{item_id}/stage",
                json={"stage": stage},
            )
            resp.raise_for_status()
            return resp.text
```

- [ ] **Step 2: Commit**

```bash
git add rm-tools/opdrachten.py
git commit -m "feat: add Opdrachten Scanner tool — inbox, pipeline, library, stats"
```

---

## Task 9: Tool Registration Script

**Files:**

- Create: `rm-tools/register_tools.py`

- [ ] **Step 1: Create the registration script**

```python
#!/usr/bin/env python3
"""
Register all Ruimtemeesters tools with OpenWebUI.

Usage:
    python rm-tools/register_tools.py --url http://localhost:3333 --token <admin-jwt>

The admin JWT can be obtained from the browser after logging in (localStorage.token
or the 'token' cookie).
"""

import argparse
import json
import os
import re
import sys

import requests

TOOL_FILES = [
    ("rm_databank", "Ruimtemeesters Databank", "rm-tools/databank.py"),
    ("rm_geoportaal", "Ruimtemeesters Geoportaal", "rm-tools/geoportaal.py"),
    ("rm_tsa", "Ruimtemeesters TSA", "rm-tools/tsa.py"),
    ("rm_dashboarding", "Ruimtemeesters Dashboarding", "rm-tools/dashboarding.py"),
    ("rm_riens", "Ruimtemeesters Sales Viewer", "rm-tools/riens.py"),
    ("rm_sales_predictor", "Ruimtemeesters Sales Predictor", "rm-tools/sales_predictor.py"),
    ("rm_opdrachten", "Ruimtemeesters Opdrachten Scanner", "rm-tools/opdrachten.py"),
]


def extract_description(content: str) -> str:
    """Extract description from tool frontmatter."""
    match = re.search(r'description:\s*(.+)', content)
    return match.group(1).strip() if match else ""


def register_tool(base_url: str, token: str, tool_id: str, name: str, filepath: str) -> bool:
    """Register or update a single tool."""
    with open(filepath, "r") as f:
        content = f.read()

    description = extract_description(content)

    # Try to update first (tool might already exist)
    resp = requests.post(
        f"{base_url}/api/v1/tools/create",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": tool_id,
            "name": name,
            "content": content,
            "meta": {
                "description": description,
            },
        },
    )

    if resp.status_code == 200:
        print(f"  ✓ Registered: {name} ({tool_id})")
        return True
    elif resp.status_code == 400 and "already exists" in resp.text.lower():
        # Update existing tool
        resp = requests.post(
            f"{base_url}/api/v1/tools/{tool_id}/update",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "id": tool_id,
                "name": name,
                "content": content,
                "meta": {
                    "description": description,
                },
            },
        )
        if resp.status_code == 200:
            print(f"  ↻ Updated: {name} ({tool_id})")
            return True

    print(f"  ✗ Failed: {name} — {resp.status_code}: {resp.text[:200]}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Register RM tools with OpenWebUI")
    parser.add_argument("--url", default="http://localhost:3333", help="OpenWebUI base URL")
    parser.add_argument("--token", required=True, help="Admin JWT token")
    args = parser.parse_args()

    print(f"Registering {len(TOOL_FILES)} tools at {args.url}...\n")

    success = 0
    for tool_id, name, filepath in TOOL_FILES:
        if not os.path.exists(filepath):
            print(f"  ✗ File not found: {filepath}")
            continue
        if register_tool(args.url, args.token, tool_id, name, filepath):
            success += 1

    print(f"\n{success}/{len(TOOL_FILES)} tools registered successfully.")
    return 0 if success == len(TOOL_FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make executable**

```bash
chmod +x rm-tools/register_tools.py
```

- [ ] **Step 3: Commit**

```bash
git add rm-tools/register_tools.py
git commit -m "feat: add tool registration script for seeding tools into OpenWebUI"
```

---

## Task 10: Register Tools and Verify

- [ ] **Step 1: Get admin JWT token**

Log into https://chatbot.datameesters.nl, open browser DevTools → Console, run:

```javascript
localStorage.token;
```

Copy the token value.

- [ ] **Step 2: Run the registration script**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
python rm-tools/register_tools.py --url http://localhost:3333 --token "<paste-token>"
```

Expected: all 7 tools registered successfully.

- [ ] **Step 3: Verify tools appear in OpenWebUI**

Open https://chatbot.datameesters.nl → Workspace → Tools. All 7 RM tools should be listed.

- [ ] **Step 4: Test a tool invocation**

Start a chat, enable the Databank tool, and ask:

> "Zoek beleidsstukken over luchtkwaliteit"

The LLM should call `search_beleidsdocumenten` and return results.

- [ ] **Step 5: Commit and push**

```bash
git add -A
git commit -m "feat: register all RM tools — verified in OpenWebUI"
git push -u origin rm/tool-integrations
```

---

## Task 11: Create PR and Merge

- [ ] **Step 1: Create PR**

```bash
gh pr create --repo Schravenralph/ruimtemeesters-browser-chatbot-staging \
  --base main --head rm/tool-integrations \
  --title "Phase A3: Tool integrations for all Ruimtemeesters apps" \
  --body "..."
```

- [ ] **Step 2: Address review feedback**

- [ ] **Step 3: Merge**

---

## Summary

After completing this plan:

- 7 OpenWebUI Tools registered, each connecting to one RM app
- Tools callable by the LLM during conversations via native function calling
- Each tool has configurable Valves for API URLs
- Registration script for easy re-deployment
- All tools follow the same pattern: httpx async calls, Pydantic Valves, reST docstrings

**Deferred to later:** Aggregator cross-app tools (A4) — these depend on Aggregator endpoints being extended first. The current Aggregator only connects to Databank + Geoportaal. Once cross-app endpoints are added to the Aggregator repo, a separate `aggregator.py` tool can be created following the same pattern.

**Next plan:** Phase A5+A6 — Assistants, prompts, audit logging, docs
