# MCP Servers Auth & Corrections — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix port/path mismatches in 5 MCP servers, add API key auth to all 5 unprotected servers, add API key middleware to Sales Predictor backend, and clean up Riens raw fetch.

**Architecture:** All changes are in the existing `Ruimtemeesters-MCP-Servers` monorepo (port defaults, env var wiring, one new shared helper) plus one FastAPI middleware addition in the `Sales-Predictor` repo.

**Tech Stack:** TypeScript (MCP servers), Python/FastAPI (Sales Predictor backend), pnpm workspaces

**Spec reference:** `docs/superpowers/specs/2026-04-02-mcp-servers-auth-and-corrections.md`

---

## File Structure

### MCP Servers repo (`/home/ralph/Projects/Ruimtemeesters-MCP-Servers/`)

| File                                     | Change                                 |
| ---------------------------------------- | -------------------------------------- |
| `packages/shared/src/http.ts`            | Add `apiPut()` function                |
| `packages/shared/src/index.ts`           | Export `apiPut`                        |
| `packages/tsa/src/server.ts`             | Port 8100, `/v1/` in all 6 paths       |
| `packages/geoportaal/src/server.ts`      | Port 5002/api, add API key             |
| `packages/dashboarding/src/server.ts`    | Port 5022, add API key                 |
| `packages/riens/src/server.ts`           | Port 3001, add API key, use `apiPut()` |
| `packages/sales-predictor/src/server.ts` | Port 8000, add API key                 |
| `packages/opdrachten/src/server.ts`      | Add API key                            |
| `.env.example`                           | Correct URLs, add all API key vars     |
| `claude-code-config.json`                | Correct URLs, add API key env vars     |

### Sales Predictor repo (`/home/ralph/Projects/Sales-Predictor/`)

| File             | Change                                |
| ---------------- | ------------------------------------- |
| `backend_api.py` | Add `SERVICE_API_KEY` HTTP middleware |

---

## Task 1: Add `apiPut` to shared HTTP client

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/shared/src/http.ts:40-63`
- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/shared/src/index.ts:1`

- [ ] **Step 1: Add `apiPut()` to `http.ts`**

Add after the `apiPost` function (after line 63):

```typescript
export async function apiPut(opts: HttpOptions, path: string, body: unknown): Promise<string> {
	const url = new URL(path, opts.baseUrl);

	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (opts.apiKey) headers['X-API-Key'] = opts.apiKey;

	const resp = await fetch(url, {
		method: 'PUT',
		headers,
		body: JSON.stringify(body),
		signal: AbortSignal.timeout(opts.timeout ?? 30_000)
	});

	if (!resp.ok) {
		const text = await resp.text().catch(() => '');
		throw new Error(`${resp.status} ${resp.statusText}: ${text.slice(0, 200)}`);
	}

	return resp.text();
}
```

- [ ] **Step 2: Export `apiPut` from `index.ts`**

Change line 1 of `packages/shared/src/index.ts` from:

```typescript
export { apiGet, apiPost, type HttpOptions } from './http.js';
```

to:

```typescript
export { apiGet, apiPost, apiPut, type HttpOptions } from './http.js';
```

- [ ] **Step 3: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/shared/tsconfig.json
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/shared/src/http.ts packages/shared/src/index.ts
git commit -m "feat(shared): add apiPut helper for PUT requests"
```

---

## Task 2: Fix TSA MCP server — port and API paths

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/tsa/src/server.ts`

- [ ] **Step 1: Fix port default**

Change line 8 from:

```typescript
  baseUrl: process.env.TSA_API_URL ?? 'http://localhost:8000',
```

to:

```typescript
  baseUrl: process.env.TSA_API_URL ?? 'http://localhost:8100',
```

- [ ] **Step 2: Fix all 6 API paths — add `/v1/`**

Change all endpoint paths:

Line 17: `/api/forecast/bevolking` → `/api/v1/forecast/bevolking`
Line 24: `/api/forecast/${geo_code}` → `/api/v1/forecast/${geo_code}`
Line 31: `/api/backtest/bevolking` → `/api/v1/backtest/bevolking`
Line 38: `/api/diagnostics/${geo_code}` → `/api/v1/diagnostics/${geo_code}`
Line 43: `/api/gemeenten` → `/api/v1/gemeenten`
Line 48: `/api/models/status` → `/api/v1/models/status`

- [ ] **Step 3: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/tsa/tsconfig.json
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/tsa/src/server.ts
git commit -m "fix(tsa): correct port to 8100 and add /v1/ to all API paths"
```

---

## Task 3: Fix Geoportaal MCP server — port and auth

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/geoportaal/src/server.ts`

- [ ] **Step 1: Fix port and add API key**

Change line 7 from:

```typescript
const opts: HttpOptions = { baseUrl: process.env.GEOPORTAAL_API_URL ?? 'http://localhost:3000' };
```

to:

```typescript
const opts: HttpOptions = {
	baseUrl: process.env.GEOPORTAAL_API_URL ?? 'http://localhost:5002/api',
	apiKey: process.env.GEOPORTAAL_API_KEY
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/geoportaal/tsconfig.json
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/geoportaal/src/server.ts
git commit -m "fix(geoportaal): correct port to 5002/api, add API key auth"
```

---

## Task 4: Fix Dashboarding MCP server — port and auth

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/dashboarding/src/server.ts`

- [ ] **Step 1: Fix port and add API key**

Change line 7 from:

```typescript
const opts: HttpOptions = { baseUrl: process.env.DASHBOARDING_API_URL ?? 'http://localhost:3003' };
```

to:

```typescript
const opts: HttpOptions = {
	baseUrl: process.env.DASHBOARDING_API_URL ?? 'http://localhost:5022',
	apiKey: process.env.DASHBOARDING_API_KEY
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/dashboarding/tsconfig.json
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/dashboarding/src/server.ts
git commit -m "fix(dashboarding): correct port to 5022, add API key auth"
```

---

## Task 5: Fix Riens MCP server — port, auth, and use `apiPut`

**Depends on:** Task 1 (apiPut in shared package)

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/riens/src/server.ts`

- [ ] **Step 1: Replace entire server.ts**

Replace the full contents of `packages/riens/src/server.ts` with:

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { startServer } from '@rm-mcp/shared';

import { z } from 'zod';
import { apiGet, apiPut, type HttpOptions } from '@rm-mcp/shared';

const opts: HttpOptions = {
	baseUrl: process.env.RIENS_API_URL ?? 'http://localhost:3001',
	apiKey: process.env.RIENS_API_KEY
};
const server = new McpServer({ name: 'rm-riens', version: '1.0.0' });

server.tool(
	'get_gemeente_status',
	'Get contract status of all Dutch municipalities — active, archived, by province',
	{},
	async () => {
		const text = await apiGet(opts, '/api/municipalities');
		return { content: [{ type: 'text' as const, text }] };
	}
);

server.tool(
	'update_gemeente',
	'Update status or notes for a municipality',
	{
		municipality_name: z.string().describe('Municipality name'),
		status: z.string().default('').describe("New status: 'active', 'archived', 'prospect'"),
		notes: z.string().default('').describe('Optional notes')
	},
	async ({ municipality_name, status, notes }) => {
		const body: Record<string, string> = {};
		if (status) body.status = status;
		if (notes) body.notes = notes;
		const text = await apiPut(opts, `/api/municipalities/${municipality_name}`, body);
		return { content: [{ type: 'text' as const, text }] };
	}
);

// Start server
await startServer(server);
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/riens/tsconfig.json
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/riens/src/server.ts
git commit -m "fix(riens): correct port to 3001, add API key, use apiPut instead of raw fetch"
```

---

## Task 6: Fix Sales Predictor MCP server — port and auth

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/sales-predictor/src/server.ts`

- [ ] **Step 1: Fix port and add API key**

Change line 7 from:

```typescript
const opts: HttpOptions = {
	baseUrl: process.env.SALES_PREDICTOR_API_URL ?? 'http://localhost:8001',
	timeout: 120_000
};
```

to:

```typescript
const opts: HttpOptions = {
	baseUrl: process.env.SALES_PREDICTOR_API_URL ?? 'http://localhost:8000',
	apiKey: process.env.SALES_PREDICTOR_API_KEY,
	timeout: 120_000
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/sales-predictor/tsconfig.json
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/sales-predictor/src/server.ts
git commit -m "fix(sales-predictor): correct port to 8000, add API key auth"
```

---

## Task 7: Fix Opdrachten MCP server — add auth

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/opdrachten/src/server.ts`

- [ ] **Step 1: Add API key**

Change line 7 from:

```typescript
const opts: HttpOptions = { baseUrl: process.env.OPDRACHTEN_API_URL ?? 'http://localhost:6300' };
```

to:

```typescript
const opts: HttpOptions = {
	baseUrl: process.env.OPDRACHTEN_API_URL ?? 'http://localhost:6300',
	apiKey: process.env.OPDRACHTEN_API_KEY
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit -p packages/opdrachten/tsconfig.json
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/opdrachten/src/server.ts
git commit -m "fix(opdrachten): add API key auth"
```

---

## Task 8: Add API key middleware to Sales Predictor backend

**Files:**

- Modify: `/home/ralph/Projects/Sales-Predictor/backend_api.py`

- [ ] **Step 1: Add the API key middleware**

Add after the CORS middleware block (after line 30) and before the router registrations (before line 33):

```python
# API key middleware
import os
import hmac
from fastapi import Request
from fastapi.responses import JSONResponse

SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if not SERVICE_API_KEY:
        return await call_next(request)
    if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    api_key = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(api_key, SERVICE_API_KEY):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)
```

- [ ] **Step 2: Add the import for `os` and `hmac` to the top imports**

Check if `os` is already imported. If not, add it. The `Request` and `JSONResponse` imports can stay inline or be moved to the top — either works for FastAPI.

Actually, `os` and `hmac` are stdlib so they should be at the top of the file. Reorganize the imports at the top of the file (lines 7-10) to:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import hmac
import logging
import os
```

Then the middleware block (inserted after CORS) becomes just:

```python
# API key middleware
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if not SERVICE_API_KEY:
        return await call_next(request)
    if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    api_key = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(api_key, SERVICE_API_KEY):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)
```

- [ ] **Step 3: Verify it starts**

```bash
cd /home/ralph/Projects/Sales-Predictor && python -c "from backend_api import app; print('OK')"
```

Expected: prints `OK` without errors.

- [ ] **Step 4: Quick manual test — without SERVICE_API_KEY set, all routes still work**

```bash
cd /home/ralph/Projects/Sales-Predictor && SERVICE_API_KEY="" python -c "
from fastapi.testclient import TestClient
from backend_api import app
client = TestClient(app)
r = client.get('/health')
print(f'health: {r.status_code}')
r = client.get('/')
print(f'root: {r.status_code}')
"
```

Expected: both print `200`.

- [ ] **Step 5: Quick manual test — with SERVICE_API_KEY set, protected routes require key**

```bash
cd /home/ralph/Projects/Sales-Predictor && SERVICE_API_KEY="test-key-123" python -c "
from fastapi.testclient import TestClient
import os
os.environ['SERVICE_API_KEY'] = 'test-key-123'
# Re-import to pick up env
import importlib
import backend_api
importlib.reload(backend_api)
client = TestClient(backend_api.app)
# Health should pass without key
r = client.get('/health')
print(f'health no key: {r.status_code}')
# API route without key should 401
r = client.get('/api/models/status')
print(f'api no key: {r.status_code}')
# API route with correct key should pass
r = client.get('/api/models/status', headers={'x-api-key': 'test-key-123'})
print(f'api with key: {r.status_code}')
# API route with wrong key should 401
r = client.get('/api/models/status', headers={'x-api-key': 'wrong'})
print(f'api wrong key: {r.status_code}')
"
```

Expected: `health no key: 200`, `api no key: 401`, `api with key: 200`, `api wrong key: 401`.

- [ ] **Step 6: Commit**

```bash
cd /home/ralph/Projects/Sales-Predictor
git add backend_api.py
git commit -m "feat: add SERVICE_API_KEY middleware — protects all API routes"
```

---

## Task 9: Update .env.example

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/.env.example`

- [ ] **Step 1: Replace .env.example contents**

```env
# App API URLs
DATABANK_API_URL=http://localhost:4000
GEOPORTAAL_API_URL=http://localhost:5002/api
TSA_API_URL=http://localhost:8100
DASHBOARDING_API_URL=http://localhost:5022
RIENS_API_URL=http://localhost:3001
SALES_PREDICTOR_API_URL=http://localhost:8000
OPDRACHTEN_API_URL=http://localhost:6300
AGGREGATOR_API_URL=http://localhost:6000

# API Keys (each app validates against its own SERVICE_API_KEY env var)
DATABANK_AUTH_TOKEN=
GEOPORTAAL_API_KEY=
TSA_API_KEY=
DASHBOARDING_API_KEY=
RIENS_API_KEY=
SALES_PREDICTOR_API_KEY=
OPDRACHTEN_API_KEY=
AGGREGATOR_API_KEY=
```

- [ ] **Step 2: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add .env.example
git commit -m "fix: update .env.example with correct ports and all API key vars"
```

---

## Task 10: Update claude-code-config.json

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/claude-code-config.json`

- [ ] **Step 1: Replace claude-code-config.json contents**

```json
{
	"mcpServers": {
		"rm-databank": {
			"command": "npx",
			"args": ["tsx", "packages/databank/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"DATABANK_API_URL": "http://localhost:4000",
				"DATABANK_AUTH_TOKEN": ""
			}
		},
		"rm-geoportaal": {
			"command": "npx",
			"args": ["tsx", "packages/geoportaal/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"GEOPORTAAL_API_URL": "http://localhost:5002/api",
				"GEOPORTAAL_API_KEY": ""
			}
		},
		"rm-tsa": {
			"command": "npx",
			"args": ["tsx", "packages/tsa/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"TSA_API_URL": "http://localhost:8100",
				"TSA_API_KEY": ""
			}
		},
		"rm-dashboarding": {
			"command": "npx",
			"args": ["tsx", "packages/dashboarding/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"DASHBOARDING_API_URL": "http://localhost:5022",
				"DASHBOARDING_API_KEY": ""
			}
		},
		"rm-riens": {
			"command": "npx",
			"args": ["tsx", "packages/riens/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"RIENS_API_URL": "http://localhost:3001",
				"RIENS_API_KEY": ""
			}
		},
		"rm-sales-predictor": {
			"command": "npx",
			"args": ["tsx", "packages/sales-predictor/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"SALES_PREDICTOR_API_URL": "http://localhost:8000",
				"SALES_PREDICTOR_API_KEY": ""
			}
		},
		"rm-opdrachten": {
			"command": "npx",
			"args": ["tsx", "packages/opdrachten/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"OPDRACHTEN_API_URL": "http://localhost:6300",
				"OPDRACHTEN_API_KEY": ""
			}
		},
		"rm-aggregator": {
			"command": "npx",
			"args": ["tsx", "packages/aggregator/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": {
				"AGGREGATOR_API_URL": "http://localhost:6000",
				"AGGREGATOR_API_KEY": ""
			}
		}
	}
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add claude-code-config.json
git commit -m "fix: update claude-code-config with correct ports and API key env vars"
```

---

## Task Dependencies

```
Task 1 (apiPut) ──→ Task 5 (Riens)
                                      ──→ Task 9 (.env.example) ──→ Task 10 (config)
Tasks 2, 3, 4, 6, 7 (parallel)       ──┘
Task 8 (Sales Predictor backend, independent)
```

Tasks 2, 3, 4, 6, 7, and 8 can all run in parallel. Task 5 depends on Task 1. Tasks 9 and 10 come last.

---

## Summary

After completing this plan:

- **5 MCP servers** have corrected default ports/URLs
- **5 MCP servers** gain API key auth (joining the 3 that already had it)
- **TSA** has correct `/api/v1/` paths for all 6 endpoints
- **Riens** uses shared `apiPut()` instead of raw `fetch()`
- **Sales Predictor backend** is protected with `SERVICE_API_KEY` middleware
- **All 8 MCP servers** consistently send `X-API-Key` when configured
- **Config files** (`.env.example`, `claude-code-config.json`) match reality
