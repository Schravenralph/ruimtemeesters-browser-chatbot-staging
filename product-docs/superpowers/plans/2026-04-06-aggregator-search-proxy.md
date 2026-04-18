# Aggregator Search Proxy + Geoportaal Enrichment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Aggregator's stub ILIKE search endpoints with a proxy to the Databank's real hybrid search API, enriched with Geoportaal spatial rules when the query mentions a Dutch municipality — and rename `POST /v1/documents/search` to `POST /v1/search/metadata-search` to clarify it's a search _type_, not a sub-resource.

**Architecture:** The Aggregator's `/v1/search/semantic` and `/v1/search/hybrid` endpoints currently stub out with `ILIKE` title matching. The Databank at `:4000` has a production-quality `GET /api/search` endpoint that combines pgvector similarity, BM25 keyword search, and knowledge graph entity matching. Since `/api/search` is a GET endpoint, it bypasses the CSRF issue that blocks POST endpoints. The Aggregator adds cross-sectional value by detecting municipality names in the query, looking up their centroid via `bevoegdgezag_geometries`, and fetching DSO spatial rules from the Geoportaal database at that coordinate.

**Tech Stack:** Node 22 (built-in `fetch`), Express, Zod, TypeScript ESM, PostgreSQL (pg)

**Repos:**

- Aggregator: `/home/ralph/Projects/Ruimtemeesters-Aggregator`
- MCP Server: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/aggregator`

---

## File Structure

| File                                  | Action    | Responsibility                                                                           |
| ------------------------------------- | --------- | ---------------------------------------------------------------------------------------- |
| `src/services/municipality-lookup.ts` | Create    | Load municipality names + centroids from DB, match names in query text                   |
| `src/services/spatial-enrichment.ts`  | Create    | Fetch Geoportaal DSO regels at a coordinate (extracted from context.ts)                  |
| `src/routes/semantic-search.ts`       | Rewrite   | Proxy to Databank `/api/search` + enrich with spatial rules                              |
| `src/routes/documents.ts`             | Modify    | Remove `POST /search` handler (moved to semantic-search.ts)                              |
| `src/index.ts`                        | No change | Already mounts `semanticSearchRouter` at `/v1/search`                                    |
| MCP `src/server.ts`                   | Modify    | Point `search_documents` at new `/v1/search/metadata-search`, add `search_semantic` tool |

---

### Task 1: Create municipality lookup service

**Files:**

- Create: `src/services/municipality-lookup.ts`

This service loads all municipality names and centroids into memory at startup (~350 rows), then provides a function to detect municipality names in a search query and return the centroid coordinates for spatial enrichment.

- [ ] **Step 1: Create the municipality lookup module**

Create `src/services/municipality-lookup.ts`:

```typescript
import { databankQuery } from '../config/database.js';
import { log } from '../config/logger.js';

interface Municipality {
	naam: string;
	lon: number;
	lat: number;
}

let municipalities: Municipality[] = [];
let loaded = false;

/**
 * Load all municipality names + centroids from bevoegdgezag_geometries.
 * Called once at startup; ~350 rows, cached in memory.
 */
export async function loadMunicipalities(): Promise<void> {
	const result = await databankQuery<{ naam: string; lon: number; lat: number }>(
		`SELECT bg.naam,
            ST_X(ST_Transform(ST_Centroid(bg.geometry), 4326)) AS lon,
            ST_Y(ST_Transform(ST_Centroid(bg.geometry), 4326)) AS lat
     FROM canonical.bevoegdgezag_geometries bg
     WHERE bg.geometry IS NOT NULL`,
		[]
	);
	municipalities = result.rows;
	loaded = true;
	log.info(`Loaded ${municipalities.length} municipalities for location detection`);
}

/**
 * Detect a municipality name in the query text.
 * Returns the first match with its centroid, or null.
 * Matches are case-insensitive and word-boundary aware.
 */
export function detectMunicipality(query: string): Municipality | null {
	if (!loaded) return null;

	const lower = query.toLowerCase();

	// Sort by name length descending so "Bergen op Zoom" matches before "Bergen"
	const sorted = [...municipalities].sort((a, b) => b.naam.length - a.naam.length);

	for (const m of sorted) {
		const nameLower = m.naam.toLowerCase();
		const idx = lower.indexOf(nameLower);
		if (idx === -1) continue;

		// Check word boundaries: character before and after must be non-alpha
		const before = idx === 0 || !/\p{L}/u.test(lower[idx - 1]);
		const after =
			idx + nameLower.length >= lower.length || !/\p{L}/u.test(lower[idx + nameLower.length]);

		if (before && after) {
			return m;
		}
	}

	return null;
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/services/municipality-lookup.ts
git commit -m "feat: add municipality lookup service for location detection in search queries"
```

---

### Task 2: Create spatial enrichment service

**Files:**

- Create: `src/services/spatial-enrichment.ts`

This extracts the Geoportaal DSO regels query from `context.ts` into a reusable function. The search proxy will call this when a municipality is detected.

- [ ] **Step 1: Create the spatial enrichment module**

Create `src/services/spatial-enrichment.ts`:

```typescript
import { geoportaalQuery } from '../config/database.js';
import { log } from '../config/logger.js';

export interface SpatialRule {
	id: number;
	w_id: string;
	label: string;
	node_type: string;
	regeling_id: number;
	activiteit_naam: string;
	activiteit_groep: string;
}

/**
 * Fetch DSO spatial rules (artikelen + activiteiten) at a WGS84 coordinate
 * from the Geoportaal database. Same query as /v1/context/at but isolated
 * for reuse by the search proxy.
 */
export async function fetchSpatialRulesAtPoint(
	lon: number,
	lat: number,
	limit = 50
): Promise<SpatialRule[]> {
	try {
		const result = await geoportaalQuery<SpatialRule>(
			`SELECT art.id, art.w_id, art.label, art.node_type, art.regeling_id,
              act.naam AS activiteit_naam, act.groep AS activiteit_groep
       FROM dso_artikel art
       JOIN dso_artikel_activiteit aa ON aa.artikel_id = art.id
       JOIN dso_activiteit act ON act.id = aa.activiteit_id
       JOIN dso_activiteit_locatie al ON al.activiteit_id = act.id
       JOIN dso_locatie l ON l.id = al.locatie_id
       WHERE ST_Intersects(l.geometry, ST_SetSRID(ST_MakePoint($1, $2), 4326))
       ORDER BY art.sort_order
       LIMIT $3`,
			[lon, lat, limit]
		);
		return result.rows;
	} catch (err) {
		log.warn(`Spatial enrichment failed at (${lon}, ${lat}):`, err);
		return [];
	}
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/services/spatial-enrichment.ts
git commit -m "feat: add spatial enrichment service for Geoportaal DSO rules lookup"
```

---

### Task 3: Rewrite semantic-search.ts — proxy to Databank + enrichment

**Files:**

- Rewrite: `src/routes/semantic-search.ts`

Replace the ILIKE stubs with:

1. Proxy to Databank `GET /api/search`
2. Detect municipality in query → fetch spatial rules from Geoportaal
3. Add `POST /v1/search/metadata-search` (moved from documents.ts)

- [ ] **Step 1: Rewrite the full file**

Replace the entire contents of `src/routes/semantic-search.ts` with:

```typescript
import { Router } from 'express';
import { z } from 'zod';
import { databankGet } from '../config/databank-client.js';
import { databankQuery } from '../config/database.js';
import { log } from '../config/logger.js';
import { detectMunicipality } from '../services/municipality-lookup.js';
import { fetchSpatialRulesAtPoint } from '../services/spatial-enrichment.js';

export const semanticSearchRouter: Router = Router();

// ---------------------------------------------------------------------------
// Types for Databank /api/search response
// ---------------------------------------------------------------------------

interface DatabankSearchDocument {
	id: string;
	content: string;
	score: number;
	metadata: Record<string, unknown>;
	uri?: string;
	sourceUrl?: string;
	rankScore?: number;
}

interface DatabankSearchEntity {
	id: string;
	name: string;
	type?: string;
	metadata?: Record<string, unknown>;
}

interface DatabankSearchResponse {
	documents: DatabankSearchDocument[];
	relatedEntities: DatabankSearchEntity[];
	hasMore: boolean;
	limit: number;
}

// ---------------------------------------------------------------------------
// POST /v1/search/semantic — proxy to Databank hybrid search + spatial enrichment
// POST /v1/search/hybrid  — same endpoint (Databank search is already hybrid)
// ---------------------------------------------------------------------------
const searchSchema = z.object({
	q: z.string().min(1),
	limit: z.number().int().min(1).max(100).default(20),
	filters: z
		.object({
			documentType: z.string().optional(),
			publisherAuthority: z.string().optional()
		})
		.optional()
});

async function handleSearch(req: import('express').Request, res: import('express').Response) {
	try {
		const parsed = searchSchema.safeParse(req.body);
		if (!parsed.success) {
			res.status(400).json({ error: 'Invalid body', details: parsed.error.flatten().fieldErrors });
			return;
		}
		const { q, limit, filters } = parsed.data;

		// Build Databank search params
		const params: Record<string, string | number> = { q, limit };
		if (filters?.documentType) params.documentType = filters.documentType;
		if (filters?.publisherAuthority) params.publisherAuthority = filters.publisherAuthority;

		// Detect municipality in query for spatial enrichment
		const municipality = detectMunicipality(q);

		// Run Databank search + spatial enrichment in parallel
		const [searchResult, spatialRules] = await Promise.all([
			databankGet<DatabankSearchResponse>('/api/search', { params }),
			municipality
				? fetchSpatialRulesAtPoint(municipality.lon, municipality.lat)
				: Promise.resolve([])
		]);

		res.json({
			documents: searchResult.documents,
			relatedEntities: searchResult.relatedEntities,
			hasMore: searchResult.hasMore,
			count: searchResult.documents.length,
			searchType: 'hybrid',
			...(municipality && {
				spatialContext: {
					municipality: municipality.naam,
					coordinate: { lon: municipality.lon, lat: municipality.lat },
					regels: {
						count: spatialRules.length,
						data: spatialRules
					}
				}
			})
		});
	} catch (err) {
		log.error(`POST /v1/search failed`, err);
		res.status(502).json({ error: 'Search request to Databank failed' });
	}
}

semanticSearchRouter.post('/semantic', handleSearch);
semanticSearchRouter.post('/hybrid', handleSearch);

// ---------------------------------------------------------------------------
// POST /v1/search/metadata-search — full-text search on document metadata
// (moved from /v1/documents/search)
// ---------------------------------------------------------------------------
const metadataSearchSchema = z.object({
	q: z.string().min(1),
	jurisdiction: z.string().optional(),
	validFrom: z.string().optional(),
	validTo: z.string().optional(),
	limit: z.coerce.number().int().min(1).max(500).default(50),
	offset: z.coerce.number().int().min(0).default(0)
});

semanticSearchRouter.post('/metadata-search', async (req, res) => {
	try {
		const parsed = metadataSearchSchema.safeParse(req.body);
		if (!parsed.success) {
			res
				.status(400)
				.json({ error: 'Invalid request body', details: parsed.error.flatten().fieldErrors });
			return;
		}

		const { q, jurisdiction, validFrom, validTo, limit, offset } = parsed.data;

		const conditions: string[] = [`d.search_vector @@ plainto_tsquery('dutch', $1)`];
		const params: unknown[] = [q];
		let idx = 2;

		if (jurisdiction) {
			conditions.push(`d.publisher_authority = $${idx++}`);
			params.push(jurisdiction);
		}
		if (validFrom) {
			conditions.push(`(d.dates->>'valid_from')::date >= $${idx++}::date`);
			params.push(validFrom);
		}
		if (validTo) {
			conditions.push(`(d.dates->>'valid_to')::date <= $${idx++}::date`);
			params.push(validTo);
		}

		const where = `WHERE ${conditions.join(' AND ')}`;

		const [countResult, dataResult] = await Promise.all([
			databankQuery<{ count: string }>(
				`SELECT count(*) AS count FROM canonical.documents d ${where}`,
				params
			),
			databankQuery(
				`SELECT d.id, d.source, d.source_id, d.title, d.document_family, d.document_type,
                d.publisher_authority, d.canonical_url, d.dates, d.format,
                d.review_status, d.tags, d.created_at, d.updated_at,
                CASE WHEN d.geometry IS NOT NULL THEN true ELSE false END AS has_geometry,
                ts_rank(d.search_vector, plainto_tsquery('dutch', $1)) AS rank
         FROM canonical.documents d
         ${where}
         ORDER BY rank DESC, d.updated_at DESC
         LIMIT $${idx++} OFFSET $${idx++}`,
				[...params, limit, offset]
			)
		]);

		res.json({
			total: parseInt(countResult.rows[0].count, 10),
			limit,
			offset,
			data: dataResult.rows
		});
	} catch (err) {
		log.error('POST /v1/search/metadata-search failed', err);
		res.status(500).json({ error: 'Internal server error' });
	}
});
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/routes/semantic-search.ts
git commit -m "feat: proxy search to Databank API with Geoportaal spatial enrichment

Replace ILIKE stubs with real hybrid search via Databank /api/search.
Auto-detect municipality names in queries and enrich with DSO spatial rules.
Add /v1/search/metadata-search (moved from /v1/documents/search)."
```

---

### Task 4: Remove POST /search from documents.ts + add redirect

**Files:**

- Modify: `src/routes/documents.ts`

Remove the `POST /v1/documents/search` handler since it's now at `/v1/search/metadata-search`. Add a 301 redirect for backwards compatibility.

- [ ] **Step 1: Replace the POST /search handler with a redirect**

In `src/routes/documents.ts`, replace lines 104-175 (the entire `POST /v1/documents/search` block, from the comment header through the closing `});`) with:

```typescript
// ---------------------------------------------------------------------------
// POST /v1/documents/search — MOVED to /v1/search/metadata-search
// Redirect kept for backwards compatibility with existing clients.
// ---------------------------------------------------------------------------
documentsRouter.post('/search', (_req, res) => {
	res.redirect(308, '/v1/search/metadata-search');
});
```

Note: HTTP 308 preserves the POST method across the redirect (unlike 301 which may change to GET).

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/routes/documents.ts
git commit -m "refactor: redirect POST /v1/documents/search to /v1/search/metadata-search"
```

---

### Task 5: Load municipalities at startup

**Files:**

- Modify: `src/index.ts`

Call `loadMunicipalities()` during startup so the location detection cache is warm before the first search request.

- [ ] **Step 1: Add the import and startup call**

In `src/index.ts`, add the import after the existing imports (after line 14):

```typescript
import { loadMunicipalities } from './services/municipality-lookup.js';
```

Then, after the `server.listen` callback (after the `log.info` on line 47), add:

```typescript
loadMunicipalities().catch((err) => log.warn('Failed to load municipalities:', err));
```

The full listen block should become:

```typescript
const server = app.listen(env.PORT, () => {
	log.info(`Aggregator Gateway listening on :${env.PORT}`);
	loadMunicipalities().catch((err) => log.warn('Failed to load municipalities:', err));
});
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-Aggregator && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/index.ts
git commit -m "feat: load municipality cache at startup for search location detection"
```

---

### Task 6: Update MCP server tool definitions

**Files:**

- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/packages/aggregator/src/server.ts`

Update `search_documents` to point at the new endpoint and add a new `search_semantic` tool for the enriched search.

- [ ] **Step 1: Update the search_documents tool**

In `server.ts`, replace lines 33-42 (the `search_documents` tool definition) with:

```typescript
server.tool(
	'search_documents',
	'Full-text search across Databank document metadata (titles, publishers, dates)',
	{
		query: z.string().describe('Search text in Dutch'),
		municipality_code: z.string().default('').describe('Optional CBS code'),
		limit: z.number().int().min(1).max(500).default(20).describe('Max results')
	},
	async ({ query, municipality_code, limit }) => {
		const body: Record<string, unknown> = { q: query, limit };
		if (municipality_code) body.jurisdiction = municipality_code;
		const text = await apiPost(opts, '/v1/search/metadata-search', body);
		return { content: [{ type: 'text' as const, text }] };
	}
);
```

- [ ] **Step 2: Add the search_semantic tool**

After the updated `search_documents` tool (and before the `get_document_summary` tool on line 44), add:

```typescript
server.tool(
	'search_semantic',
	'Semantic search across document content — uses vector similarity + keyword matching + knowledge graph. Auto-enriches with spatial rules when query mentions a municipality.',
	{
		query: z.string().describe('Search text in Dutch'),
		limit: z.number().int().min(1).max(100).default(20).describe('Max results'),
		document_type: z.string().default('').describe('Optional document type filter'),
		publisher_authority: z.string().default('').describe('Optional publisher/authority filter')
	},
	async ({ query, limit, document_type, publisher_authority }) => {
		const body: Record<string, unknown> = { q: query, limit };
		const filters: Record<string, string> = {};
		if (document_type) filters.documentType = document_type;
		if (publisher_authority) filters.publisherAuthority = publisher_authority;
		if (Object.keys(filters).length > 0) body.filters = filters;
		const text = await apiPost(opts, '/v1/search/semantic', body);
		return { content: [{ type: 'text' as const, text }] };
	}
);
```

- [ ] **Step 3: Verify it compiles**

Run: `cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && npx tsc --noEmit`
Expected: no errors (adjust command if the project uses a different build setup)

- [ ] **Step 4: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add packages/aggregator/src/server.ts
git commit -m "feat: add search_semantic tool, update search_documents to use metadata-search endpoint"
```

---

### Task 7: Rebuild and smoke test

- [ ] **Step 1: Rebuild the Aggregator container**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
docker compose up -d --build
```

- [ ] **Step 2: Wait for healthy status**

```bash
docker ps --filter name=ruimtemeesters-aggregator --format '{{.Status}}'
```

Expected: `Up ... (healthy)` within 30 seconds

- [ ] **Step 3: Test semantic search**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  http://localhost:6000/v1/search/semantic \
  -d '{"q":"bruidsschat","limit":5}' | python3 -m json.tool
```

Expected: `searchType: "hybrid"`, `documents` array with scored results from Databank, `relatedEntities` array. No `spatialContext` (no municipality in query).

- [ ] **Step 4: Test semantic search with municipality enrichment**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  http://localhost:6000/v1/search/semantic \
  -d '{"q":"bruidsschat Amsterdam","limit":5}' | python3 -m json.tool
```

Expected: Same as step 3, plus `spatialContext` object with `municipality: "Amsterdam"`, `coordinate`, and `regels` array with DSO artikelen/activiteiten.

- [ ] **Step 5: Test hybrid search (same behavior)**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  http://localhost:6000/v1/search/hybrid \
  -d '{"q":"omgevingsplan","limit":3}' | python3 -m json.tool
```

Expected: Same response structure as semantic search.

- [ ] **Step 6: Test metadata-search**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  http://localhost:6000/v1/search/metadata-search \
  -d '{"q":"omgevingsplan","limit":5}' | python3 -m json.tool
```

Expected: `total`, `limit`, `offset`, `data` array with document metadata + `rank` score. Same response shape as old `/v1/documents/search`.

- [ ] **Step 7: Test backwards-compat redirect**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  -L http://localhost:6000/v1/documents/search \
  -d '{"q":"omgevingsplan","limit":5}' | python3 -m json.tool
```

Expected: Same response as step 6 (curl follows the 308 redirect).

- [ ] **Step 8: Test search with filters**

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: aggregator-dev-key-2026" \
  http://localhost:6000/v1/search/semantic \
  -d '{"q":"geluid","limit":5,"filters":{"documentType":"Omgevingsvisie"}}' | python3 -m json.tool
```

Expected: Filtered results — only documents of type `Omgevingsvisie`.

---

### Task 8: Update the aggregator semantic search issue

**Files:**

- Modify: `product-docs/20-issues/2026-04-05-aggregator-semantic-search-stub.md` (in Browser-Chatbot repo)

- [ ] **Step 1: Mark the issue as resolved**

Add a `## Resolution` section at the bottom of the file:

```markdown
## Resolution

**Date:** 2026-04-06

Aggregator search endpoints now proxy to Databank `GET /api/search` (real hybrid vector+keyword+KG search). Municipality names in queries trigger automatic Geoportaal spatial rule enrichment. The old `POST /v1/documents/search` was renamed to `POST /v1/search/metadata-search` with a 308 redirect for backwards compatibility.
```

- [ ] **Step 2: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
git add product-docs/20-issues/2026-04-05-aggregator-semantic-search-stub.md
git commit -m "docs: mark aggregator semantic search stub issue as resolved"
```
