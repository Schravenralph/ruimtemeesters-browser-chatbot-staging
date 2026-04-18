# Phase C1+C2+C3: MCP Servers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a dedicated repo with 8 MCP servers (one per app + aggregator) exposing all Ruimtemeesters app capabilities via the Model Context Protocol.

**Architecture:** pnpm monorepo with a shared package (auth, HTTP client, schemas) and 8 per-app MCP server packages. Each server wraps the same REST API endpoints as the Phase A OpenWebUI Tools, but via MCP protocol. Servers support both stdio (for Claude Code/Cursor) and SSE (for remote clients) transport.

**Tech Stack:** TypeScript, `@modelcontextprotocol/server`, Zod v4, pnpm workspaces, tsx (dev), Docker

**Spec reference:** `docs/superpowers/specs/2026-04-01-phase-c-mcp-extension-layer.md`

---

## File Structure

### Root

| File                  | Responsibility                      |
| --------------------- | ----------------------------------- |
| `pnpm-workspace.yaml` | Workspace definition                |
| `tsconfig.base.json`  | Shared TypeScript config            |
| `package.json`        | Root package with workspace scripts |
| `.env.example`        | Environment template                |
| `docker-compose.yaml` | Run all MCP servers                 |
| `README.md`           | Usage docs                          |

### packages/shared/

| File             | Responsibility                                        |
| ---------------- | ----------------------------------------------------- |
| `src/http.ts`    | Shared async HTTP client with error handling          |
| `src/schemas.ts` | Common Zod schemas (gemeente code, bbox, coordinates) |
| `src/index.ts`   | Barrel export                                         |
| `package.json`   | Package config                                        |
| `tsconfig.json`  | Extends base                                          |

### packages/{app}/ (one per app)

| File            | Responsibility                                |
| --------------- | --------------------------------------------- |
| `src/server.ts` | MCP server entry point with tool registration |
| `package.json`  | Package config with bin entry                 |
| `tsconfig.json` | Extends base                                  |

---

## Task 1: Create repo and workspace infrastructure

**Files:**

- Create: `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json`, `.env.example`, `.gitignore`, `README.md`

- [ ] **Step 1: Create the repo on GitHub**

```bash
cd /home/ralph/Projects
gh repo create Schravenralph/Ruimtemeesters-MCP-Servers --public --clone
cd Ruimtemeesters-MCP-Servers
```

- [ ] **Step 2: Create root package.json**

```json
{
	"name": "ruimtemeesters-mcp-servers",
	"private": true,
	"scripts": {
		"dev:databank": "pnpm --filter @rm-mcp/databank dev",
		"dev:geoportaal": "pnpm --filter @rm-mcp/geoportaal dev",
		"dev:tsa": "pnpm --filter @rm-mcp/tsa dev",
		"dev:dashboarding": "pnpm --filter @rm-mcp/dashboarding dev",
		"dev:riens": "pnpm --filter @rm-mcp/riens dev",
		"dev:sales-predictor": "pnpm --filter @rm-mcp/sales-predictor dev",
		"dev:opdrachten": "pnpm --filter @rm-mcp/opdrachten dev",
		"dev:aggregator": "pnpm --filter @rm-mcp/aggregator dev",
		"build": "pnpm -r build",
		"typecheck": "pnpm -r typecheck"
	}
}
```

- [ ] **Step 3: Create pnpm-workspace.yaml**

```yaml
packages:
  - 'packages/*'
```

- [ ] **Step 4: Create tsconfig.base.json**

```json
{
	"compilerOptions": {
		"target": "ES2022",
		"module": "Node16",
		"moduleResolution": "Node16",
		"esModuleInterop": true,
		"strict": true,
		"skipLibCheck": true,
		"outDir": "dist",
		"rootDir": "src",
		"declaration": true,
		"sourceMap": true
	}
}
```

- [ ] **Step 5: Create .env.example**

```env
# App API URLs
DATABANK_API_URL=http://localhost:4000
GEOPORTAAL_API_URL=http://localhost:3000
TSA_API_URL=http://localhost:8000
DASHBOARDING_API_URL=http://localhost:3003
RIENS_API_URL=http://localhost:7707
SALES_PREDICTOR_API_URL=http://localhost:8001
OPDRACHTEN_API_URL=http://localhost:6300
AGGREGATOR_API_URL=http://localhost:6000

# API Keys (for apps that require them)
TSA_API_KEY=
AGGREGATOR_API_KEY=
```

- [ ] **Step 6: Create .gitignore**

```
node_modules/
dist/
.env
*.tsbuildinfo
```

- [ ] **Step 7: Create README.md**

```markdown
# Ruimtemeesters MCP Servers

MCP (Model Context Protocol) servers for all Ruimtemeesters applications.
Usable from Claude Code, Cursor, OpenWebUI, and any MCP-compatible client.

## Quick Start

\`\`\`bash
pnpm install
cp .env.example .env

# Edit .env with your API URLs

# Run a single server (stdio mode for Claude Code)

pnpm dev:databank

# Run all servers (Docker)

docker compose up
\`\`\`

## Adding to Claude Code

Add to your `.claude.json` or `claude_desktop_config.json`:

\`\`\`json
{
"mcpServers": {
"rm-databank": {
"command": "npx",
"args": ["tsx", "packages/databank/src/server.ts"]
}
}
}
\`\`\`
```

- [ ] **Step 8: Initialize and commit**

```bash
pnpm init
git add -A
git commit -m "chore: initialize MCP servers monorepo with pnpm workspace"
```

---

## Task 2: Shared package

**Files:**

- Create: `packages/shared/package.json`, `packages/shared/tsconfig.json`, `packages/shared/src/http.ts`, `packages/shared/src/schemas.ts`, `packages/shared/src/index.ts`

- [ ] **Step 1: Create packages/shared/package.json**

```json
{
	"name": "@rm-mcp/shared",
	"version": "1.0.0",
	"private": true,
	"type": "module",
	"exports": {
		".": "./src/index.ts"
	},
	"dependencies": {
		"zod": "^3.25.0"
	}
}
```

- [ ] **Step 2: Create packages/shared/tsconfig.json**

```json
{
	"extends": "../../tsconfig.base.json",
	"compilerOptions": {
		"outDir": "dist",
		"rootDir": "src"
	},
	"include": ["src"]
}
```

- [ ] **Step 3: Create packages/shared/src/http.ts**

```typescript
/**
 * Shared HTTP client for MCP servers.
 * All app API calls go through this.
 */

export interface HttpOptions {
	baseUrl: string;
	apiKey?: string;
	timeout?: number;
}

export async function apiGet(
	opts: HttpOptions,
	path: string,
	params?: Record<string, string | number>
): Promise<string> {
	const url = new URL(path, opts.baseUrl);
	if (params) {
		for (const [k, v] of Object.entries(params)) {
			if (v !== undefined && v !== '') url.searchParams.set(k, String(v));
		}
	}

	const headers: Record<string, string> = {};
	if (opts.apiKey) headers['X-API-Key'] = opts.apiKey;

	const resp = await fetch(url, {
		headers,
		signal: AbortSignal.timeout(opts.timeout ?? 30_000)
	});

	if (!resp.ok) {
		const body = await resp.text().catch(() => '');
		throw new Error(`${resp.status} ${resp.statusText}: ${body.slice(0, 200)}`);
	}

	return resp.text();
}

export async function apiPost(opts: HttpOptions, path: string, body: unknown): Promise<string> {
	const url = new URL(path, opts.baseUrl);

	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (opts.apiKey) headers['X-API-Key'] = opts.apiKey;

	const resp = await fetch(url, {
		method: 'POST',
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

- [ ] **Step 4: Create packages/shared/src/schemas.ts**

```typescript
import { z } from 'zod';

/** CBS gemeente code, e.g. 'gm0363' or 'GM0363' */
export const gemeenteCodeSchema = z
	.string()
	.regex(/^[gG][mM]\d{4}$/)
	.describe('CBS gemeente code, e.g. gm0363 for Amsterdam');

/** WGS84 longitude */
export const lonSchema = z.number().min(-180).max(180).describe('Longitude in WGS84');

/** WGS84 latitude */
export const latSchema = z.number().min(-90).max(90).describe('Latitude in WGS84');

/** Bounding box as comma-separated string */
export const bboxSchema = z
	.string()
	.regex(/^-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*$/)
	.describe('Bounding box as minlon,minlat,maxlon,maxlat in WGS84');

/** Pagination limit */
export const limitSchema = z
	.number()
	.int()
	.min(1)
	.max(500)
	.default(20)
	.describe('Maximum number of results');
```

- [ ] **Step 5: Create packages/shared/src/index.ts**

```typescript
export { apiGet, apiPost, type HttpOptions } from './http.js';
export { gemeenteCodeSchema, lonSchema, latSchema, bboxSchema, limitSchema } from './schemas.js';
```

- [ ] **Step 6: Install and commit**

```bash
pnpm install
git add packages/shared/
git commit -m "feat: add shared package — HTTP client and common Zod schemas"
```

---

## Task 3: Databank MCP Server (template for all others)

**Files:**

- Create: `packages/databank/package.json`, `packages/databank/tsconfig.json`, `packages/databank/src/server.ts`

- [ ] **Step 1: Create packages/databank/package.json**

```json
{
	"name": "@rm-mcp/databank",
	"version": "1.0.0",
	"private": true,
	"type": "module",
	"bin": {
		"rm-mcp-databank": "src/server.ts"
	},
	"scripts": {
		"dev": "tsx src/server.ts"
	},
	"dependencies": {
		"@modelcontextprotocol/sdk": "^1.12.0",
		"@rm-mcp/shared": "workspace:*",
		"zod": "^3.25.0"
	},
	"devDependencies": {
		"tsx": "^4.19.0",
		"typescript": "^5.7.0"
	}
}
```

- [ ] **Step 2: Create packages/databank/tsconfig.json**

```json
{
	"extends": "../../tsconfig.base.json",
	"compilerOptions": {
		"outDir": "dist",
		"rootDir": "src"
	},
	"include": ["src"]
}
```

- [ ] **Step 3: Create packages/databank/src/server.ts**

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { apiGet, apiPost, type HttpOptions } from '@rm-mcp/shared';

const API_URL = process.env.DATABANK_API_URL ?? 'http://localhost:4000';
const opts: HttpOptions = { baseUrl: API_URL };

const server = new McpServer({
	name: 'rm-databank',
	version: '1.0.0'
});

server.tool(
	'search_beleidsdocumenten',
	'Search for Dutch policy documents (beleidsstukken) using hybrid keyword and semantic search',
	{
		query: z
			.string()
			.describe("Search query in Dutch, e.g. 'luchtkwaliteit' or 'woningbouw Den Haag'"),
		location: z.string().default('').describe('Optional municipality or region name'),
		document_type: z.string().default('').describe('Optional document type filter'),
		limit: z.number().int().min(1).max(100).default(10).describe('Maximum results')
	},
	async ({ query, location, document_type, limit }) => {
		const params: Record<string, string | number> = { q: query, limit };
		if (location) params.location = location;
		if (document_type) params.documentType = document_type;
		const text = await apiGet(opts, '/api/search', params);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_knowledge_graph',
	'Query the Databank knowledge graph to explore relationships between policies, topics, and municipalities',
	{
		entity_id: z
			.string()
			.default('')
			.describe('Optional entity ID for specific entity with neighbors. Leave empty for overview.')
	},
	async ({ entity_id }) => {
		const text = entity_id
			? await apiGet(opts, `/api/knowledge-graph/entity/${entity_id}`)
			: await apiGet(opts, '/api/knowledge-graph', { limit: 50 });
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_document',
	'Get the full details of a specific canonical document from the Databank',
	{ document_id: z.string().describe('The document ID to retrieve') },
	async ({ document_id }) => {
		const text = await apiGet(opts, `/api/canonical-documents/${document_id}`);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'list_queries',
	"List the user's beleidsscan queries (policy scan searches)",
	{},
	async () => {
		const text = await apiGet(opts, '/api/queries');
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'create_query',
	'Start a new beleidsscan query to search for and analyze policy documents',
	{
		search_text: z.string().describe("Policy topic to search, e.g. 'luchtkwaliteit maatregelen'"),
		location: z.string().default('').describe('Optional municipality to scope the search')
	},
	async ({ search_text, location }) => {
		const body: Record<string, string> = { searchText: search_text };
		if (location) body.location = location;
		const text = await apiPost(opts, '/api/queries', body);
		return { content: [{ type: 'text', text }] };
	}
);

// --- Start server ---
const transport = new StdioServerTransport();
await server.connect(transport);
```

- [ ] **Step 4: Install dependencies and test**

```bash
pnpm install
pnpm dev:databank
# Should start without errors (will fail to connect to API but MCP server starts)
# Press Ctrl+C to stop
```

- [ ] **Step 5: Commit**

```bash
git add packages/databank/
git commit -m "feat: add Databank MCP server — search beleid, knowledge graph, queries"
```

---

## Task 4: Geoportaal MCP Server

**Files:**

- Create: `packages/geoportaal/package.json`, `packages/geoportaal/tsconfig.json`, `packages/geoportaal/src/server.ts`

- [ ] **Step 1: Create package.json** (same structure as databank, name `@rm-mcp/geoportaal`, bin `rm-mcp-geoportaal`, dev script same)

- [ ] **Step 2: Create tsconfig.json** (identical to databank)

- [ ] **Step 3: Create packages/geoportaal/src/server.ts**

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { apiGet, type HttpOptions } from '@rm-mcp/shared';

const API_URL = process.env.GEOPORTAAL_API_URL ?? 'http://localhost:3000';
const opts: HttpOptions = { baseUrl: API_URL };

const server = new McpServer({ name: 'rm-geoportaal', version: '1.0.0' });

server.tool(
	'query_spatial_rules',
	'Look up spatial planning rules (omgevingsregels) for a location or policy area',
	{
		query: z
			.string()
			.default('')
			.describe("Search text for rules, e.g. 'bouwhoogte centrum Amsterdam'"),
		rule_id: z.string().default('').describe('Optional specific rule ID')
	},
	async ({ query, rule_id }) => {
		const text = rule_id
			? await apiGet(opts, `/v1/rules/${rule_id}`)
			: await apiGet(opts, '/v1/rules', query ? { q: query } : {});
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_air_quality',
	'Get air quality (luchtkwaliteit) data for a location',
	{
		location: z.string().default('').describe('Municipality name or location')
	},
	async ({ location }) => {
		const text = await apiGet(opts, '/v1/air-quality', location ? { location } : {});
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_weather',
	'Get current weather data for a location in the Netherlands',
	{
		location: z.string().default('').describe('Municipality name or location')
	},
	async ({ location }) => {
		const text = await apiGet(opts, '/v1/weather', location ? { location } : {});
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_building_data',
	'Get 3D building data (3DBAG) including heights and categories',
	{
		location: z.string().default('').describe('Address or location')
	},
	async ({ location }) => {
		const text = await apiGet(opts, '/v1/building', location ? { location } : {});
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'search_documents',
	'Search spatial documents and policy maps',
	{
		query: z.string().describe('Search text')
	},
	async ({ query }) => {
		const text = await apiGet(opts, '/search', { q: query });
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'search_pdok',
	'Search PDOK (Kadaster) national geo-datasets',
	{
		query: z.string().describe('Search text for PDOK datasets')
	},
	async ({ query }) => {
		const text = await apiGet(opts, '/v1/pdok/search', { q: query });
		return { content: [{ type: 'text', text }] };
	}
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

- [ ] **Step 4: Commit**

```bash
git add packages/geoportaal/
git commit -m "feat: add Geoportaal MCP server — spatial rules, air quality, weather, buildings, PDOK"
```

---

## Task 5: TSA MCP Server

**Files:**

- Create: `packages/tsa/package.json`, `packages/tsa/tsconfig.json`, `packages/tsa/src/server.ts`

- [ ] **Step 1: Create package.json and tsconfig.json** (same pattern, name `@rm-mcp/tsa`)

- [ ] **Step 2: Create packages/tsa/src/server.ts**

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { apiGet, apiPost, type HttpOptions } from '@rm-mcp/shared';

const API_URL = process.env.TSA_API_URL ?? 'http://localhost:8000';
const API_KEY = process.env.TSA_API_KEY ?? '';
const opts: HttpOptions = { baseUrl: API_URL, apiKey: API_KEY, timeout: 120_000 };

const server = new McpServer({ name: 'rm-tsa', version: '1.0.0' });

server.tool(
	'run_population_forecast',
	'Run demographic population forecast using ML ensemble (Prophet, SARIMA, Holt-Winters, State-Space)',
	{
		geo_code: z.string().describe("CBS gemeente code, e.g. 'GM0363' for Amsterdam")
	},
	async ({ geo_code }) => {
		const text = await apiPost(opts, '/api/forecast/bevolking', { geo_code });
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_forecast_results',
	'Get cached forecast results for a municipality',
	{
		geo_code: z.string().describe("CBS gemeente code, e.g. 'GM0363'")
	},
	async ({ geo_code }) => {
		const text = await apiGet(opts, `/api/forecast/${geo_code}`);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'run_backtest',
	'Run walk-forward backtest to validate forecast accuracy',
	{
		geo_code: z.string().describe('CBS gemeente code')
	},
	async ({ geo_code }) => {
		const text = await apiPost(opts, '/api/backtest/bevolking', { geo_code });
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_diagnostics',
	'Get forecast diagnostics — model performance and data quality',
	{
		geo_code: z.string().describe('CBS gemeente code')
	},
	async ({ geo_code }) => {
		const text = await apiGet(opts, `/api/diagnostics/${geo_code}`);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool('list_gemeenten', 'List all Dutch municipalities with CBS codes', {}, async () => {
	const text = await apiGet(opts, '/api/gemeenten');
	return { content: [{ type: 'text', text }] };
});

server.tool(
	'get_model_status',
	'Get available forecast models and latest run status',
	{},
	async () => {
		const text = await apiGet(opts, '/api/models/status');
		return { content: [{ type: 'text', text }] };
	}
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

- [ ] **Step 3: Commit**

```bash
git add packages/tsa/
git commit -m "feat: add TSA MCP server — forecasts, backtests, diagnostics"
```

---

## Task 6: Remaining MCP Servers (Dashboarding, Riens, Sales Predictor, Opdrachten)

**Files:**

- Create: `packages/dashboarding/`, `packages/riens/`, `packages/sales-predictor/`, `packages/opdrachten/` (same structure)

- [ ] **Step 1: Create all 4 servers**

Each follows the same package.json/tsconfig.json pattern. Server files translate directly from the Phase A Python tools (`rm-tools/*.py`) — same tool names, same parameters, same API endpoints.

**packages/dashboarding/src/server.ts** — 4 tools: `get_dashboard_data`, `get_statistics`, `get_trends`, `search_dashboard`

- Env: `DASHBOARDING_API_URL` (default `http://localhost:3003`)
- Endpoints: `/api/data`, `/api/stats`, `/api/trends`, `/api/search`

**packages/riens/src/server.ts** — 2 tools: `get_gemeente_status`, `update_gemeente`

- Env: `RIENS_API_URL` (default `http://localhost:7707`)
- Endpoints: GET `/api/municipalities`, PUT `/api/municipalities/:name`

**packages/sales-predictor/src/server.ts** — 4 tools: `run_sales_forecast`, `get_predictions`, `compare_models`, `list_models`

- Env: `SALES_PREDICTOR_API_URL` (default `http://localhost:8001`)
- Endpoints: POST `/api/train`, POST `/api/predict`, GET `/api/comparison`, GET `/api/models`

**packages/opdrachten/src/server.ts** — 7 tools: `get_inbox`, `get_pipeline`, `get_pipeline_deadlines`, `search_library`, `get_stats`, `accept_inbox_item`, `move_pipeline_stage`

- Env: `OPDRACHTEN_API_URL` (default `http://localhost:6300`)
- Endpoints: GET `/api/inbox`, GET `/api/pipeline`, GET `/api/pipeline/deadlines`, GET `/api/library`, GET `/api/stats`, POST `/api/inbox/:id/accept`, POST `/api/pipeline/:id/stage`

- [ ] **Step 2: Install and verify each starts**

```bash
pnpm install
pnpm dev:dashboarding  # Ctrl+C
pnpm dev:riens         # Ctrl+C
pnpm dev:sales-predictor # Ctrl+C
pnpm dev:opdrachten    # Ctrl+C
```

- [ ] **Step 3: Commit each**

```bash
git add packages/dashboarding/ && git commit -m "feat: add Dashboarding MCP server"
git add packages/riens/ && git commit -m "feat: add Riens Sales Viewer MCP server"
git add packages/sales-predictor/ && git commit -m "feat: add Sales Predictor MCP server"
git add packages/opdrachten/ && git commit -m "feat: add Opdrachten Scanner MCP server"
```

---

## Task 7: Aggregator MCP Server

**Files:**

- Create: `packages/aggregator/package.json`, `packages/aggregator/tsconfig.json`, `packages/aggregator/src/server.ts`

- [ ] **Step 1: Create packages/aggregator/src/server.ts**

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { apiGet, apiPost, type HttpOptions } from '@rm-mcp/shared';

const API_URL = process.env.AGGREGATOR_API_URL ?? 'http://localhost:6000';
const API_KEY = process.env.AGGREGATOR_API_KEY ?? '';
const opts: HttpOptions = { baseUrl: API_URL, apiKey: API_KEY };

const server = new McpServer({ name: 'rm-aggregator', version: '1.0.0' });

// Cross-app context
server.tool(
	'context_at_coordinate',
	'Get full context at a coordinate — combines Databank documents with Geoportaal spatial rules',
	{
		lon: z.number().min(-180).max(180).describe('Longitude (WGS84)'),
		lat: z.number().min(-90).max(90).describe('Latitude (WGS84)'),
		project_id: z.number().int().default(0).describe('Optional Geoportaal project ID')
	},
	async ({ lon, lat, project_id }) => {
		const params: Record<string, string | number> = { lon, lat };
		if (project_id) params.projectId = project_id;
		const text = await apiGet(opts, '/v1/context/at', params);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'context_municipality',
	'Get municipality overview — gemeente info, document counts, and rules per project',
	{
		municipality_code: z.string().describe("CBS gemeente code, e.g. 'gm0363'")
	},
	async ({ municipality_code }) => {
		const text = await apiGet(opts, `/v1/context/municipality/${municipality_code}`);
		return { content: [{ type: 'text', text }] };
	}
);

// Documents
server.tool(
	'search_documents',
	'Full-text search across Databank policy documents',
	{
		query: z.string().describe('Search text in Dutch'),
		municipality_code: z.string().default('').describe("Optional CBS code, e.g. 'gm0363'"),
		limit: z.number().int().min(1).max(500).default(20).describe('Max results')
	},
	async ({ query, municipality_code, limit }) => {
		const body: Record<string, unknown> = { q: query, limit };
		if (municipality_code) body.jurisdiction = municipality_code;
		const text = await apiPost(opts, '/v1/documents/search', body);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_document_summary',
	'Get summary of a specific document',
	{
		document_id: z.string().describe('Document UUID')
	},
	async ({ document_id }) => {
		const text = await apiGet(opts, `/v1/documents/${document_id}/summary`);
		return { content: [{ type: 'text', text }] };
	}
);

// Spatial
server.tool(
	'spatial_rules_at_point',
	'Get all DSO spatial rules at a coordinate',
	{
		lon: z.number().min(-180).max(180).describe('Longitude'),
		lat: z.number().min(-90).max(90).describe('Latitude'),
		project_id: z.number().int().default(1).describe('Geoportaal project ID')
	},
	async ({ lon, lat, project_id }) => {
		const text = await apiGet(opts, '/v1/spatial/regels', { lon, lat, projectId: project_id });
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'solar_potential',
	'Get solar energy potential for buildings in an area',
	{
		bbox: z.string().describe("Bounding box as 'minlon,minlat,maxlon,maxlat'"),
		project_id: z.number().int().default(1).describe('Geoportaal project ID')
	},
	async ({ bbox, project_id }) => {
		const text = await apiGet(opts, '/v1/spatial/solar', { bbox, projectId: project_id });
		return { content: [{ type: 'text', text }] };
	}
);

// Knowledge graph
server.tool(
	'search_knowledge_graph',
	'Search entities in the knowledge graph by name',
	{
		query: z.string().describe('Search text for entity names'),
		entity_type: z.string().default('').describe("Optional Neo4j label filter, e.g. 'Policy'"),
		limit: z.number().int().min(1).max(200).default(20).describe('Max results')
	},
	async ({ query, entity_type, limit }) => {
		const params: Record<string, string | number> = { q: query, limit };
		if (entity_type) params.type = entity_type;
		const text = await apiGet(opts, '/v1/kg/entities', params);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'get_entity_relations',
	'Get a knowledge graph entity with all its relationships',
	{
		entity_id: z.string().describe('Entity ID')
	},
	async ({ entity_id }) => {
		const text = await apiGet(opts, `/v1/kg/entity/${entity_id}`);
		return { content: [{ type: 'text', text }] };
	}
);

server.tool(
	'traverse_graph',
	'Traverse the knowledge graph from a starting entity',
	{
		start_id: z.string().describe('Starting entity ID'),
		max_depth: z.number().int().min(1).max(10).default(3).describe('Max traversal depth'),
		direction: z
			.enum(['outgoing', 'incoming', 'both'])
			.default('both')
			.describe('Relationship direction')
	},
	async ({ start_id, max_depth, direction }) => {
		const text = await apiPost(opts, '/v1/kg/traverse', {
			startId: start_id,
			maxDepth: max_depth,
			direction
		});
		return { content: [{ type: 'text', text }] };
	}
);

server.tool('graph_stats', 'Get knowledge graph statistics', {}, async () => {
	const text = await apiGet(opts, '/v1/kg/stats');
	return { content: [{ type: 'text', text }] };
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

- [ ] **Step 2: Commit**

```bash
git add packages/aggregator/
git commit -m "feat: add Aggregator MCP server — cross-app context, documents, spatial, knowledge graph"
```

---

## Task 8: Claude Code Configuration

**Files:**

- Create: `claude-code-config.json`

- [ ] **Step 1: Create example Claude Code MCP config**

```json
{
	"mcpServers": {
		"rm-databank": {
			"command": "npx",
			"args": ["tsx", "packages/databank/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": { "DATABANK_API_URL": "http://localhost:4000" }
		},
		"rm-geoportaal": {
			"command": "npx",
			"args": ["tsx", "packages/geoportaal/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": { "GEOPORTAAL_API_URL": "http://localhost:3000" }
		},
		"rm-tsa": {
			"command": "npx",
			"args": ["tsx", "packages/tsa/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": { "TSA_API_URL": "http://localhost:8000" }
		},
		"rm-aggregator": {
			"command": "npx",
			"args": ["tsx", "packages/aggregator/src/server.ts"],
			"cwd": "/home/ralph/Projects/Ruimtemeesters-MCP-Servers",
			"env": { "AGGREGATOR_API_URL": "http://localhost:6000" }
		}
	}
}
```

- [ ] **Step 2: Commit**

```bash
git add claude-code-config.json
git commit -m "feat: add Claude Code MCP server configuration"
```

---

## Task 9: Final verification and push

- [ ] **Step 1: Install all dependencies**

```bash
pnpm install
```

- [ ] **Step 2: Verify all servers start**

```bash
for pkg in databank geoportaal tsa dashboarding riens sales-predictor opdrachten aggregator; do
  echo "Testing $pkg..."
  timeout 3 pnpm dev:$pkg 2>&1 || true
done
```

- [ ] **Step 3: Push to GitHub**

```bash
git push -u origin main
```

---

## Summary

After completing this plan:

- **1 new repo** (`Ruimtemeesters-MCP-Servers`) with pnpm workspace
- **1 shared package** (`@rm-mcp/shared`) with HTTP client + Zod schemas
- **8 MCP servers** (46 tools total) matching all Phase A OpenWebUI tools
- **Claude Code config** ready to use
- All servers support stdio transport (SSE can be added later when needed)

**Next plans:**

- Phase C4: Connect OpenWebUI to MCP servers
- Phase C5: Cursor config + developer docs
