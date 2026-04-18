# Aggregator KG Proxy + Chunking Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Aggregator's knowledge graph endpoints to the Databank's real KG (10,276 entities) instead of the empty Neo4j (90 smoke-test nodes), and improve document chunk quality for chatbot Q&A.

**Architecture:** Replace direct Neo4j Cypher queries in the Aggregator with HTTP proxy calls to the Databank's `/api/knowledge-graph/*` endpoints. The Databank's GraphDB backend has the real entity data (PolicyDocument, Regulation, SpatialUnit, etc.). For entity search, proxy to the Databank's `/api/search` which returns `relatedEntities` from the KG. For traverse/path (unsupported on GraphDB), implement iterative neighbor traversal using the entity endpoint.

**Tech Stack:** Node 22 (built-in `fetch`), Express, Zod, TypeScript ESM

**Repos:** Aggregator code lives at `/home/ralph/Projects/Ruimtemeesters-Aggregator`

---

## File Structure

| File                            | Action  | Responsibility                                            |
| ------------------------------- | ------- | --------------------------------------------------------- |
| `src/config/env.ts`             | Modify  | Add `DATABANK_API_URL` and `DATABANK_API_KEY` env vars    |
| `src/config/databank-client.ts` | Create  | HTTP client for Databank API (GET/POST with API key auth) |
| `src/routes/knowledge-graph.ts` | Rewrite | Proxy all KG endpoints to Databank HTTP API               |
| `src/routes/health.ts`          | Modify  | Replace Neo4j health check with Databank KG health check  |
| `src/index.ts`                  | Modify  | Remove `shutdownNeo4j` import (Neo4j no longer used)      |
| `.env`                          | Modify  | Add `DATABANK_API_URL` and `DATABANK_API_KEY` values      |

After this change, `src/config/neo4j.ts` and `neo4j-driver` become unused and can be removed.

---

## Endpoint Mapping

| Aggregator endpoint               | Current source                | New source (Databank)                                               |
| --------------------------------- | ----------------------------- | ------------------------------------------------------------------- |
| `GET /v1/kg/stats`                | Neo4j `MATCH (n)`             | `GET /api/knowledge-graph/stats`                                    |
| `GET /v1/kg/entities?q=...`       | Neo4j `WHERE e.name CONTAINS` | `GET /api/search?q=...` → extract `relatedEntities`                 |
| `GET /v1/kg/entity/:id`           | Neo4j `WHERE e.id = $id`      | `GET /api/knowledge-graph/entity/:id`                               |
| `GET /v1/kg/entity/:id/neighbors` | Neo4j `MATCH (e)-[r]-(n)`     | Derived from entity endpoint (already returns `neighbors`)          |
| `POST /v1/kg/traverse`            | Neo4j variable-length path    | Iterative neighbor fetch (GraphDB doesn't support Cypher traversal) |
| `POST /v1/kg/path`                | Neo4j `shortestPath`          | Not supported on GraphDB → return 501 with helpful message          |
| `GET /v1/kg/clusters`             | Neo4j `labels(n), count(n)`   | `GET /api/knowledge-graph/meta?strategy=entity-type`                |

---

### Task 1: Add Databank API config to env

**Files:**

- Modify: `src/config/env.ts`
- Modify: `.env`

- [ ] **Step 1: Add env vars to schema**

In `src/config/env.ts`, add two new fields to the `envSchema` object, after the Neo4j section:

```typescript
  // Databank HTTP API (knowledge graph proxy)
  DATABANK_API_URL: z.string().url().default('http://localhost:4000'),
  DATABANK_API_KEY: z.string().default(''),
```

- [ ] **Step 2: Add values to .env**

Append to `.env`:

```
# Databank HTTP API (for knowledge graph proxy)
DATABANK_API_URL=http://ruimtemeesters-databank-backend:4000
DATABANK_API_KEY=rm-databank-service-2026
```

Note: `ruimtemeesters-databank-backend` is the Databank's Docker DNS name on the shared `ruimtemeesters-databank-network`.

- [ ] **Step 3: Verify env loads**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsx -e "import './src/config/env.js'; console.log('OK')"`
Expected: `OK` (no validation errors)

- [ ] **Step 4: Commit**

```bash
git add src/config/env.ts .env
git commit -m "feat: add DATABANK_API_URL and DATABANK_API_KEY to aggregator env"
```

---

### Task 2: Create Databank HTTP client

**Files:**

- Create: `src/config/databank-client.ts`

- [ ] **Step 1: Create the HTTP client module**

```typescript
import { env } from './env.js';
import { log } from './logger.js';

export interface DatabankRequestOptions {
	/** Query string parameters */
	params?: Record<string, string | number>;
	/** JSON body for POST requests */
	body?: unknown;
	/** Timeout in ms (default 15000) */
	timeout?: number;
}

/**
 * GET request to the Databank HTTP API.
 * Auth via X-API-Key header.
 */
export async function databankGet<T = unknown>(
	path: string,
	opts: DatabankRequestOptions = {}
): Promise<T> {
	const url = new URL(path, env.DATABANK_API_URL);
	if (opts.params) {
		for (const [k, v] of Object.entries(opts.params)) {
			url.searchParams.set(k, String(v));
		}
	}

	const start = Date.now();
	const res = await fetch(url, {
		method: 'GET',
		headers: {
			'X-API-Key': env.DATABANK_API_KEY,
			Accept: 'application/json'
		},
		signal: AbortSignal.timeout(opts.timeout ?? 15_000)
	});

	if (!res.ok) {
		const text = await res.text().catch(() => '');
		log.error(`databankGet ${path} → ${res.status}: ${text.slice(0, 200)}`);
		throw new Error(`Databank API ${res.status}: ${text.slice(0, 200)}`);
	}

	const data = (await res.json()) as T;
	log.debug(`databankGet ${path} ${Date.now() - start}ms`);
	return data;
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/config/databank-client.ts
git commit -m "feat: add Databank HTTP client for KG proxy"
```

---

### Task 3: Rewrite KG routes to proxy to Databank

**Files:**

- Rewrite: `src/routes/knowledge-graph.ts`

This is the core change. Replace all Neo4j Cypher queries with Databank HTTP API calls.

- [ ] **Step 1: Rewrite the full file**

Replace the entire contents of `src/routes/knowledge-graph.ts` with:

```typescript
import { Router } from 'express';
import { z } from 'zod';
import { databankGet } from '../config/databank-client.js';
import { log } from '../config/logger.js';

export const knowledgeGraphRouter: Router = Router();

// ---------------------------------------------------------------------------
// Type definitions for Databank API responses
// ---------------------------------------------------------------------------

interface DatabankEntity {
	id: string;
	type: string;
	name: string;
	metadata?: Record<string, unknown>;
	[key: string]: unknown;
}

interface DatabankEntityResponse extends DatabankEntity {
	neighbors: {
		incoming: DatabankEntity[];
		outgoing: DatabankEntity[];
	};
}

interface DatabankSearchResponse {
	documents: Array<{
		id: string;
		content: string;
		score: number;
		metadata: Record<string, unknown>;
	}>;
	relatedEntities: DatabankEntity[];
	meta?: Record<string, unknown>;
}

interface DatabankStatsResponse {
	nodeCount: number;
	edgeCount: number;
	typeDistribution: Record<string, number>;
	relationshipTypeDistribution: Record<string, number>;
}

interface DatabankMetaCluster {
	id: string;
	label: string;
	nodeCount: number;
	[key: string]: unknown;
}

interface DatabankMetaResponse {
	clusters: Record<string, DatabankMetaCluster>;
}

// ---------------------------------------------------------------------------
// GET /v1/kg/stats — knowledge graph statistics
// ---------------------------------------------------------------------------
knowledgeGraphRouter.get('/stats', async (_req, res) => {
	try {
		const stats = await databankGet<DatabankStatsResponse>('/api/knowledge-graph/stats');

		// Map to existing response format for backwards compatibility
		const nodesByType = Object.entries(stats.typeDistribution).map(([type, count]) => ({
			types: [type],
			count
		}));
		const relationshipsByType = Object.entries(stats.relationshipTypeDistribution).map(
			([type, count]) => ({
				type,
				count
			})
		);

		res.json({
			totalNodes: stats.nodeCount,
			totalRelationships: stats.edgeCount,
			nodesByType,
			relationshipsByType
		});
	} catch (err) {
		log.error('GET /v1/kg/stats failed', err);
		res.status(502).json({ error: 'Failed to fetch KG stats from Databank' });
	}
});

// ---------------------------------------------------------------------------
// GET /v1/kg/entities?q=...&type=...&limit=50 — search entities
// ---------------------------------------------------------------------------
const entitiesSchema = z.object({
	q: z.string().min(1),
	type: z.string().optional(),
	limit: z.coerce.number().int().min(1).max(200).default(50)
});

knowledgeGraphRouter.get('/entities', async (req, res) => {
	try {
		const parsed = entitiesSchema.safeParse(req.query);
		if (!parsed.success) {
			res
				.status(400)
				.json({ error: 'Invalid query parameters', details: parsed.error.flatten().fieldErrors });
			return;
		}
		const { q, type, limit } = parsed.data;

		// Use Databank's semantic search which returns relatedEntities from the KG
		const searchResult = await databankGet<DatabankSearchResponse>('/api/search', {
			params: { q, limit: Math.min(limit, 100) }
		});

		let entities = searchResult.relatedEntities ?? [];

		// Filter by type if specified
		if (type) {
			entities = entities.filter((e) => e.type === type);
		}

		// Respect limit
		entities = entities.slice(0, limit);

		res.json({ count: entities.length, data: entities });
	} catch (err) {
		log.error('GET /v1/kg/entities failed', err);
		res.status(502).json({ error: 'Failed to search KG entities via Databank' });
	}
});

// ---------------------------------------------------------------------------
// GET /v1/kg/entity/:id — entity with relationships
// ---------------------------------------------------------------------------
knowledgeGraphRouter.get('/entity/:id', async (req, res) => {
	try {
		const { id } = req.params;
		const entity = await databankGet<DatabankEntityResponse>(
			`/api/knowledge-graph/entity/${encodeURIComponent(id)}`
		);

		// Map to existing response format
		const relations = [
			...entity.neighbors.incoming.map((n) => ({ relation: 'incoming', target: n })),
			...entity.neighbors.outgoing.map((n) => ({ relation: 'outgoing', target: n }))
		];

		const { neighbors: _, ...entityProps } = entity;
		res.json({ entity: entityProps, relations });
	} catch (err: any) {
		if (err?.message?.includes('404')) {
			res.status(404).json({ error: 'Entity not found' });
			return;
		}
		log.error('GET /v1/kg/entity/:id failed', err);
		res.status(502).json({ error: 'Failed to fetch entity from Databank' });
	}
});

// ---------------------------------------------------------------------------
// GET /v1/kg/entity/:id/neighbors — 1-hop neighbors
// ---------------------------------------------------------------------------
const neighborsSchema = z.object({
	limit: z.coerce.number().int().min(1).max(200).default(50)
});

knowledgeGraphRouter.get('/entity/:id/neighbors', async (req, res) => {
	try {
		const { id } = req.params;
		const parsed = neighborsSchema.safeParse(req.query);
		if (!parsed.success) {
			res
				.status(400)
				.json({ error: 'Invalid query parameters', details: parsed.error.flatten().fieldErrors });
			return;
		}
		const { limit } = parsed.data;

		const entity = await databankGet<DatabankEntityResponse>(
			`/api/knowledge-graph/entity/${encodeURIComponent(id)}`
		);

		const allNeighbors = [
			...entity.neighbors.incoming.map((n) => ({ node: n, relation: 'incoming' })),
			...entity.neighbors.outgoing.map((n) => ({ node: n, relation: 'outgoing' }))
		].slice(0, limit);

		res.json({ count: allNeighbors.length, data: allNeighbors });
	} catch (err: any) {
		if (err?.message?.includes('404')) {
			res.status(404).json({ error: 'Entity not found' });
			return;
		}
		log.error('GET /v1/kg/entity/:id/neighbors failed', err);
		res.status(502).json({ error: 'Failed to fetch neighbors from Databank' });
	}
});

// ---------------------------------------------------------------------------
// POST /v1/kg/traverse — graph traversal via iterative neighbor fetch
// ---------------------------------------------------------------------------
const traverseSchema = z.object({
	startId: z.string(),
	maxDepth: z.number().int().min(1).max(5).default(2),
	relationTypes: z.array(z.string()).optional(),
	direction: z.enum(['outgoing', 'incoming', 'both']).default('both')
});

knowledgeGraphRouter.post('/traverse', async (req, res) => {
	try {
		const parsed = traverseSchema.safeParse(req.body);
		if (!parsed.success) {
			res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten().fieldErrors });
			return;
		}
		const { startId, maxDepth, direction } = parsed.data;

		// BFS traversal using the entity endpoint
		const visited = new Map<string, DatabankEntity>();
		const edges: Array<{ source: string; target: string; relation: string }> = [];
		let frontier = [startId];

		for (let depth = 0; depth < maxDepth && frontier.length > 0; depth++) {
			const nextFrontier: string[] = [];

			// Fetch neighbors for each node in the frontier (max 10 concurrent)
			const batch = frontier.slice(0, 10);
			const results = await Promise.allSettled(
				batch.map((id) =>
					databankGet<DatabankEntityResponse>(
						`/api/knowledge-graph/entity/${encodeURIComponent(id)}`
					)
				)
			);

			for (let i = 0; i < results.length; i++) {
				const result = results[i];
				if (result.status !== 'fulfilled') continue;

				const entity = result.value;
				const { neighbors: entityNeighbors, ...entityProps } = entity;
				if (!visited.has(entity.id)) {
					visited.set(entity.id, entityProps);
				}

				const addNeighbors = (list: DatabankEntity[], rel: string) => {
					for (const n of list) {
						if (!visited.has(n.id)) {
							visited.set(n.id, n);
							nextFrontier.push(n.id);
						}
						edges.push({ source: entity.id, target: n.id, relation: rel });
					}
				};

				if (direction !== 'incoming') addNeighbors(entityNeighbors.outgoing, 'outgoing');
				if (direction !== 'outgoing') addNeighbors(entityNeighbors.incoming, 'incoming');
			}

			frontier = nextFrontier;
		}

		res.json({
			count: visited.size,
			nodes: [...visited.values()],
			edges,
			metadata: { startId, maxDepth, direction, depthReached: maxDepth }
		});
	} catch (err) {
		log.error('POST /v1/kg/traverse failed', err);
		res.status(502).json({ error: 'Failed to traverse graph via Databank' });
	}
});

// ---------------------------------------------------------------------------
// POST /v1/kg/path — not supported on GraphDB backend
// ---------------------------------------------------------------------------
knowledgeGraphRouter.post('/path', async (_req, res) => {
	res.status(501).json({
		error: 'Shortest path is not supported on the current GraphDB backend',
		suggestion: 'Use POST /v1/kg/traverse from each endpoint and check for overlap'
	});
});

// ---------------------------------------------------------------------------
// GET /v1/kg/clusters — entity clusters from meta endpoint
// ---------------------------------------------------------------------------
knowledgeGraphRouter.get('/clusters', async (_req, res) => {
	try {
		const meta = await databankGet<DatabankMetaResponse>('/api/knowledge-graph/meta', {
			params: { strategy: 'entity-type' }
		});

		const clusters = Object.values(meta.clusters).map((c) => ({
			labels: [c.label],
			size: c.nodeCount
		}));

		res.json({ count: clusters.length, clusters });
	} catch (err) {
		log.error('GET /v1/kg/clusters failed', err);
		res.status(502).json({ error: 'Failed to fetch clusters from Databank' });
	}
});
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/routes/knowledge-graph.ts
git commit -m "feat: proxy KG endpoints to Databank HTTP API instead of empty Neo4j"
```

---

### Task 4: Remove Neo4j dependency from health check and index

**Files:**

- Modify: `src/routes/health.ts`
- Modify: `src/index.ts`

- [ ] **Step 1: Replace Neo4j health check with Databank KG health check**

In `src/routes/health.ts`, replace the Neo4j import and health check block:

Replace import:

```typescript
import { verifyNeo4j } from '../config/neo4j.js';
```

with:

```typescript
import { databankGet } from '../config/databank-client.js';
```

Replace the Neo4j health check block (the `// Check Neo4j` section) with:

```typescript
// Check Databank KG (via HTTP API)
const kgStart = Date.now();
try {
	await databankGet('/api/knowledge-graph/stats');
	checks.knowledgeGraph = { ok: true, latencyMs: Date.now() - kgStart };
} catch (err) {
	checks.knowledgeGraph = { ok: false, error: (err as Error).message };
}
```

- [ ] **Step 2: Remove shutdownNeo4j from index.ts**

In `src/index.ts`, remove the import:

```typescript
import { shutdownNeo4j } from './config/neo4j.js';
```

And change the shutdown function's `Promise.all` from:

```typescript
await Promise.all([shutdownPools(), shutdownNeo4j()]);
```

to:

```typescript
await shutdownPools();
```

- [ ] **Step 3: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add src/routes/health.ts src/index.ts
git commit -m "refactor: replace Neo4j health check with Databank KG HTTP check"
```

---

### Task 5: Clean up unused Neo4j files and dependency

**Files:**

- Delete: `src/config/neo4j.ts`
- Modify: `package.json` (remove `neo4j-driver`)

- [ ] **Step 1: Delete neo4j.ts**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
rm src/config/neo4j.ts
```

- [ ] **Step 2: Remove neo4j-driver dependency**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
pnpm remove neo4j-driver
```

- [ ] **Step 3: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors (no file should import neo4j anymore)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove unused neo4j-driver dependency"
```

---

### Task 6: Rebuild and test the Aggregator container

- [ ] **Step 1: Rebuild the container**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
docker compose up -d --build
```

- [ ] **Step 2: Wait for healthy status**

```bash
docker ps --filter name=ruimtemeesters-aggregator --format '{{.Status}}'
```

Expected: `Up ... (healthy)` within 30 seconds

- [ ] **Step 3: Test health endpoint**

```bash
curl -s -H "X-API-Key: aggregator-dev-key-2026" http://localhost:6000/health | python3 -m json.tool
```

Expected: `"status": "healthy"` with `knowledgeGraph.ok: true`

- [ ] **Step 4: Test KG stats**

```bash
curl -s -H "X-API-Key: aggregator-dev-key-2026" http://localhost:6000/v1/kg/stats | python3 -m json.tool
```

Expected: `totalNodes: 10276`, `totalRelationships: 6019`, nodesByType includes `PolicyDocument: 8391`

- [ ] **Step 5: Test entity search**

```bash
curl -s -H "X-API-Key: aggregator-dev-key-2026" "http://localhost:6000/v1/kg/entities?q=bruidsschat&limit=5" | python3 -m json.tool
```

Expected: `count > 0`, entities with types like `Regulation`, `PolicyDocument`

- [ ] **Step 6: Test entity by ID**

Use an entity ID from step 5 and fetch it:

```bash
curl -s -H "X-API-Key: aggregator-dev-key-2026" "http://localhost:6000/v1/kg/entity/reg-8eed5ec3-reg-overgangsregels-tijdelijk-deel-omgevingsplan" | python3 -m json.tool
```

Expected: entity with `type: "Regulation"`, `name: "Overgangsregels tijdelijk deel omgevingsplan (bruidsschat)"`, plus relations array

- [ ] **Step 7: Test traverse**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" http://localhost:6000/v1/kg/traverse -d '{"startId":"reg-8eed5ec3-reg-overgangsregels-tijdelijk-deel-omgevingsplan","maxDepth":2}' | python3 -m json.tool
```

Expected: `count > 1`, nodes array with related entities, edges array

- [ ] **Step 8: Test clusters**

```bash
curl -s -H "X-API-Key: aggregator-dev-key-2026" http://localhost:6000/v1/kg/clusters | python3 -m json.tool
```

Expected: clusters with `PolicyDocument`, `Regulation`, `SpatialUnit` labels

---

### Task 7: Re-test the MCP Aggregator server

After the backend Aggregator is fixed, the MCP server (which proxies to the Aggregator) should also return correct data.

- [ ] **Step 1: Test via MCP server's HTTP endpoint (running in Docker)**

```bash
# The MCP aggregator is at rm-mcp-aggregator, proxying to ruimtemeesters-aggregator:6000
# Test the search_knowledge_graph tool concept via the Aggregator API
curl -s -H "X-API-Key: aggregator-dev-key-2026" "http://localhost:6000/v1/kg/entities?q=omgevingsplan&type=PolicyDocument&limit=5" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'Found {d[\"count\"]} entities')
for e in d['data'][:5]:
    print(f'  [{e[\"type\"]}] {e[\"name\"][:80]}')
"
```

Expected: PolicyDocument entities related to omgevingsplan

- [ ] **Step 2: Commit (if any test adjustments needed)**
