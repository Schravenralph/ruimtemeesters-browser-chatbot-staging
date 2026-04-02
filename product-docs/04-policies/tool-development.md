# Tool Development Guide

## How to add a new OpenWebUI Tool

### 1. Create the tool file

Create `rm-tools/<app-name>.py` in the staging repo following this template:

```python
"""
title: Tool Name
description: What it does
author: Ruimtemeesters
version: 1.0.0
requirements: httpx
"""

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        api_url: str = Field(default="http://app:port", description="Base URL")
        api_key: str = Field(default="", description="Service API key")
        timeout: int = Field(default=30, description="Timeout seconds")

    def __init__(self):
        self.valves = self.Valves()

    def _headers(self) -> dict:
        h: dict = {}
        if self.valves.api_key:
            h["X-API-Key"] = self.valves.api_key
        return h

    async def my_tool(self, param: str, __user__: dict = {}) -> str:
        """
        Description for the LLM.
        :param param: What this parameter is
        :return: What gets returned
        """
        async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
            resp = await client.get(
                f"{self.valves.api_url}/api/endpoint",
                params={"q": param},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text
```

### 2. Register the tool

Add it to `TOOL_FILES` in `rm-tools/register_tools.py`, then run:

```bash
python3 rm-tools/register_tools.py --url http://localhost:3333 --token <admin-jwt>
```

### 3. Configure Valves

Set the correct API URL and key via the OpenWebUI admin UI or API:

```bash
curl -X POST "http://localhost:3333/api/v1/tools/id/<tool_id>/valves/update" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"api_url":"http://host.docker.internal:<port>","api_key":"<key>","timeout":30}'
```

### 4. Add to an assistant

Update `rm-tools/register_assistants.py` to include the tool ID in the relevant assistant's `toolIds` list.

### Key rules

- **URL from inside Docker:** Use `host.docker.internal:<port>` for apps running on the host
- **Auth:** Apps need a `SERVICE_API_KEY` env var and middleware check for internal chatbot access
- **Docstrings:** Use `:param` reST format — OpenWebUI extracts these for the LLM function spec
- **`__user__` param:** Always include but don't expose to LLM (double underscore prefix is hidden)
- **Return type:** Always `str` — OpenWebUI passes the raw text to the LLM
- **Error handling:** Let `raise_for_status()` throw — OpenWebUI catches and shows the error

## How to add a new MCP Server

### 1. Create the package

```bash
cd Ruimtemeesters-MCP-Servers
mkdir -p packages/<app-name>/src
```

Create `package.json`, `tsconfig.json`, and `src/server.ts` following the existing pattern.

### 2. Register tools

Use `server.tool()` with Zod schemas for input validation.

### 3. Start modes

- **stdio:** `npx tsx packages/<app>/src/server.ts` (for Claude Code)
- **HTTP:** `npx tsx packages/<app>/src/server.ts --http --port <port>` (for OpenWebUI)

### 4. Add to OpenWebUI

Configure via `POST /api/v1/configs/tool_servers` with `type: "mcp"`.
