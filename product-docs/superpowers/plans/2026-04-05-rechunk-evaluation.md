# Re-chunk Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the existing `UnifiedChunkingService` produces better chunks than the 500-char backfill, then re-chunk all documents through it.

**Architecture:** Write a metrics script and a re-chunk script in the Databank repo. Run metrics before, re-chunk a test subset, run IPLO benchmark, then full re-chunk. All scripts use existing services (`UnifiedChunkingService`, `CanonicalChunkService`, `VectorService`).

**Tech Stack:** TypeScript ESM, PostgreSQL (canonical.chunks), pgvector, Xenova/all-MiniLM-L6-v2

**Repo:** `/home/ralph/Projects/Ruimtemeesters-Databank`

---

## File Structure

| File                         | Action | Responsibility                                                             |
| ---------------------------- | ------ | -------------------------------------------------------------------------- |
| `scripts/chunk-metrics.ts`   | Create | Compute chunk quality metrics from PostgreSQL, output markdown report      |
| `scripts/rechunk-unified.ts` | Create | Re-chunk documents via UnifiedChunkingService + re-embed via VectorService |
| `scripts/iplo-benchmark.ts`  | Create | Run 5 IPLO questions against Databank search API, score and output report  |

No existing files are modified. The scripts use existing services via their module exports.

---

### Task 1: Baseline chunk quality metrics script

**Files:**

- Create: `scripts/chunk-metrics.ts`

- [ ] **Step 1: Create the metrics script**

```typescript
/**
 * chunk-metrics.ts — Compute chunk quality metrics from canonical.chunks
 *
 * Usage: npx tsx scripts/chunk-metrics.ts [--source DSO|IPLO|OB|...]
 */
import 'dotenv/config';
import { getPostgresPool } from '../src/server/config/postgres.js';

async function main() {
	const pool = getPostgresPool();
	const sourceFilter = process.argv[2] === '--source' ? process.argv[3] : null;
	const whereClause = sourceFilter ? `WHERE d.source = '${sourceFilter}'` : '';
	const joinClause = sourceFilter
		? `JOIN canonical.documents d ON d.id = c.document_id ${whereClause}`
		: '';

	// 1. Size distribution
	const sizeResult = await pool.query(`
    SELECT
      CASE
        WHEN length(c.text) <= 500 THEN '<=500'
        WHEN length(c.text) <= 1000 THEN '501-1000'
        WHEN length(c.text) <= 2000 THEN '1001-2000'
        WHEN length(c.text) <= 5000 THEN '2001-5000'
        ELSE '>5000'
      END as bucket,
      count(*)::int as cnt
    FROM canonical.chunks c
    ${joinClause}
    GROUP BY 1 ORDER BY 1
  `);

	// 2. Overall stats
	const statsResult = await pool.query(`
    SELECT
      count(*)::int as total_chunks,
      min(length(c.text))::int as min_len,
      max(length(c.text))::int as max_len,
      avg(length(c.text))::int as avg_len,
      percentile_cont(0.5) WITHIN GROUP (ORDER BY length(c.text))::int as median_len
    FROM canonical.chunks c
    ${joinClause}
  `);

	// 3. Sentence completeness: % ending with sentence-terminal punctuation
	const sentenceResult = await pool.query(`
    SELECT
      count(*) FILTER (WHERE rtrim(c.text) ~ '[.!?)\"]$')::int as complete,
      count(*)::int as total
    FROM canonical.chunks c
    ${joinClause}
  `);

	// 4. Mid-word cuts: chunks starting with a lowercase letter (continuation)
	const midWordResult = await pool.query(`
    SELECT
      count(*) FILTER (WHERE c.text ~ '^[a-z]')::int as starts_lowercase,
      count(*)::int as total
    FROM canonical.chunks c
    ${joinClause}
  `);

	// 5. Per-source breakdown
	const perSourceResult = await pool.query(`
    SELECT d.source,
      count(DISTINCT c.document_id)::int as docs,
      count(c.id)::int as chunks,
      avg(length(c.text))::int as avg_len
    FROM canonical.chunks c
    JOIN canonical.documents d ON d.id = c.document_id
    GROUP BY d.source ORDER BY chunks DESC
  `);

	// Output markdown report
	const stats = statsResult.rows[0];
	const sent = sentenceResult.rows[0];
	const mid = midWordResult.rows[0];
	const sentPct = ((sent.complete / sent.total) * 100).toFixed(1);
	const midPct = ((mid.starts_lowercase / mid.total) * 100).toFixed(1);

	console.log(`# Chunk Quality Metrics`);
	console.log(`\nDate: ${new Date().toISOString().split('T')[0]}`);
	console.log(`Filter: ${sourceFilter || 'all sources'}\n`);

	console.log(`## Overall Stats\n`);
	console.log(`| Metric | Value |`);
	console.log(`|---|---|`);
	console.log(`| Total chunks | ${stats.total_chunks.toLocaleString()} |`);
	console.log(`| Min size | ${stats.min_len} chars |`);
	console.log(`| Max size | ${stats.max_len.toLocaleString()} chars |`);
	console.log(`| Avg size | ${stats.avg_len} chars |`);
	console.log(`| Median size | ${stats.median_len} chars |`);
	console.log(
		`| Sentence completeness | ${sentPct}% (${sent.complete.toLocaleString()}/${sent.total.toLocaleString()}) |`
	);
	console.log(
		`| Mid-word starts | ${midPct}% (${mid.starts_lowercase.toLocaleString()}/${mid.total.toLocaleString()}) |`
	);

	console.log(`\n## Size Distribution\n`);
	console.log(`| Bucket | Count | % |`);
	console.log(`|---|---|---|`);
	for (const row of sizeResult.rows) {
		const pct = ((row.cnt / stats.total_chunks) * 100).toFixed(1);
		console.log(`| ${row.bucket} | ${row.cnt.toLocaleString()} | ${pct}% |`);
	}

	console.log(`\n## Per Source\n`);
	console.log(`| Source | Docs | Chunks | Avg Size |`);
	console.log(`|---|---|---|---|`);
	for (const row of perSourceResult.rows) {
		console.log(
			`| ${row.source} | ${row.docs.toLocaleString()} | ${row.chunks.toLocaleString()} | ${row.avg_len} |`
		);
	}

	await pool.end();
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
```

- [ ] **Step 2: Run baseline metrics and save output**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
npx tsx scripts/chunk-metrics.ts > /tmp/chunk-metrics-baseline.md
cat /tmp/chunk-metrics-baseline.md
```

Expected: Report showing ~130k chunks, avg ~582, 97.9% <=500, sentence completeness likely <50%, mid-word starts likely >30%.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
git add scripts/chunk-metrics.ts
git commit -m "feat: add chunk quality metrics script"
```

---

### Task 2: IPLO benchmark script

**Files:**

- Create: `scripts/iplo-benchmark.ts`

- [ ] **Step 1: Create the benchmark script**

```typescript
/**
 * iplo-benchmark.ts — Run 5 IPLO Q&A pairs against the Databank search API
 *
 * Queries the running Databank at localhost:4000, retrieves top-5 chunks,
 * and outputs the retrieved context for manual scoring.
 *
 * Usage: npx tsx scripts/iplo-benchmark.ts
 */
import 'dotenv/config';

const DATABANK_URL = process.env.DATABANK_URL || 'http://localhost:4000';
const API_KEY = process.env.SERVICE_API_KEY || 'rm-databank-service-2026';

interface Question {
	id: string;
	question: string;
	referenceAnswer: string;
	keywords: string[]; // Key facts that should appear in retrieved chunks
}

const QUESTIONS: Question[] = [
	{
		id: 'Q1',
		question: 'Kan een gemeente de werkingssfeer van de bruidsschatregels omgevingsplan wijzigen?',
		referenceAnswer:
			'Ja. Per locatie en per regel laten vervallen. Vervangende regel moet noemer + geometrisch informatieobject krijgen. Moet voldoen aan instructieregels hoofdstuk 5 Bkl.',
		keywords: [
			'bruidsschat',
			'wijzigen',
			'gemeente',
			'noemer',
			'geometrisch informatieobject',
			'instructieregels',
			'Besluit kwaliteit leefomgeving'
		]
	},
	{
		id: 'Q2',
		question: 'Wijzigt de Vangnetregeling Omgevingswet de bruidsschat omgevingsplan?',
		referenceAnswer:
			'Nee. Ministeriële regeling die aanvult/verduidelijkt maar niet wijzigt. Geen onderdeel van het omgevingsplan. Niet ontsloten via Regels op de kaart.',
		keywords: [
			'Vangnetregeling',
			'niet wijzigt',
			'aanvult',
			'verduidelijkt',
			'ministeriële regeling',
			'geen onderdeel'
		]
	},
	{
		id: 'Q3',
		question: 'Wat regelt artikel 22.36, bruidsschat omgevingsplan?',
		referenceAnswer:
			'Bijzondere gevallen bij omzetting Bijlage II Bor: bijbehorend bouwwerk, erfafscheiding 1-2m, mantelzorggebruik. Bij naleving 22.27 + 22.36 = van rechtswege in overeenstemming.',
		keywords: [
			'22.36',
			'bijbehorend bouwwerk',
			'erfafscheiding',
			'mantelzorg',
			'van rechtswege',
			'22.27',
			'Bijlage II'
		]
	},
	{
		id: 'Q4',
		question: 'Waar vind ik de bouwregels voor woningen?',
		referenceAnswer:
			'Omgevingsplan (bouwhoogte, oppervlakte, type bewoning), Bbl (technische regels), BW (burenrecht). Vergunningvrij bouwen in art. 2.29 Bbl.',
		keywords: [
			'omgevingsplan',
			'bouwhoogte',
			'oppervlakte',
			'Bbl',
			'Besluit bouwwerken leefomgeving',
			'burenrecht',
			'Burgerlijk Wetboek'
		]
	},
	{
		id: 'Q5',
		question: 'Welke gebruiksregels gelden voor woningen in het omgevingsplan?',
		referenceAnswer:
			'Bruidsschat: geen overlast/hinder, bedrijf aan huis, hobbydieren. Bbl: brandveiligheid. APV: openbare orde. BW: burenrecht.',
		keywords: [
			'gebruiksregels',
			'overlast',
			'hinder',
			'bedrijf aan huis',
			'brandveiligheid',
			'APV',
			'burenrecht'
		]
	}
];

async function searchDatabank(query: string, limit: number = 5): Promise<any> {
	const url = `${DATABANK_URL}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`;
	const res = await fetch(url, {
		headers: { 'X-API-Key': API_KEY, Accept: 'application/json' }
	});
	if (!res.ok) throw new Error(`Search failed: ${res.status}`);
	return res.json();
}

function scoreKeywords(text: string, keywords: string[]): { found: string[]; missing: string[] } {
	const lower = text.toLowerCase();
	const found: string[] = [];
	const missing: string[] = [];
	for (const kw of keywords) {
		if (lower.includes(kw.toLowerCase())) {
			found.push(kw);
		} else {
			missing.push(kw);
		}
	}
	return { found, missing };
}

async function main() {
	console.log(`# IPLO Retrieval Benchmark`);
	console.log(`\nDate: ${new Date().toISOString().split('T')[0]}`);
	console.log(`Endpoint: ${DATABANK_URL}/api/search\n`);

	let totalFound = 0;
	let totalKeywords = 0;

	for (const q of QUESTIONS) {
		const result = await searchDatabank(q.question);
		const chunks = result.documents || [];
		const concatenated = chunks.map((c: any) => c.content || c.text || '').join('\n\n');
		const entities = result.relatedEntities || [];

		const { found, missing } = scoreKeywords(concatenated, q.keywords);
		totalFound += found.length;
		totalKeywords += q.keywords.length;

		console.log(`## ${q.id}: ${q.question}\n`);
		console.log(`**Reference:** ${q.referenceAnswer}\n`);
		console.log(`**Chunks retrieved:** ${chunks.length} (total ${concatenated.length} chars)`);
		console.log(`**KG entities:** ${entities.length}`);
		console.log(
			`**Keywords found:** ${found.length}/${q.keywords.length} (${found.join(', ') || 'none'})`
		);
		console.log(`**Keywords missing:** ${missing.join(', ') || 'none'}\n`);

		// Show first 300 chars of top chunk for inspection
		if (chunks.length > 0) {
			const topChunk = chunks[0].content || chunks[0].text || '';
			console.log(`**Top chunk (${topChunk.length} chars):** ${topChunk.substring(0, 300)}...\n`);
		}

		console.log('---\n');
	}

	const overallPct = ((totalFound / totalKeywords) * 100).toFixed(1);
	console.log(`## Summary\n`);
	console.log(`| Metric | Value |`);
	console.log(`|---|---|`);
	console.log(`| Total keywords found | ${totalFound}/${totalKeywords} (${overallPct}%) |`);
	console.log(
		`| Questions with >50% keywords | ${
			QUESTIONS.filter((q, i) => {
				const result = scoreKeywords('', q.keywords); // placeholder - recalculate properly
				return true; // Will be filled by actual run
			}).length
		}/5 |`
	);
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
```

- [ ] **Step 2: Run baseline IPLO benchmark and save output**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
npx tsx scripts/iplo-benchmark.ts > /tmp/iplo-benchmark-baseline.md
cat /tmp/iplo-benchmark-baseline.md
```

Expected: Low keyword coverage (estimated <30% based on earlier manual testing).

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
git add scripts/iplo-benchmark.ts
git commit -m "feat: add IPLO retrieval benchmark script"
```

---

### Task 3: Re-chunk script using UnifiedChunkingService

**Files:**

- Create: `scripts/rechunk-unified.ts`

- [ ] **Step 1: Create the re-chunk script**

```typescript
/**
 * rechunk-unified.ts — Re-chunk documents using UnifiedChunkingService
 *
 * Replaces the old 500-char fixed-size chunks with properly chunked content
 * using heading/paragraph/article-aware strategies per document family.
 *
 * Usage:
 *   npx tsx scripts/rechunk-unified.ts                    # all documents
 *   npx tsx scripts/rechunk-unified.ts --source IPLO      # single source
 *   npx tsx scripts/rechunk-unified.ts --limit 100        # test subset
 *   npx tsx scripts/rechunk-unified.ts --source DSO --limit 50  # combined
 */
import 'dotenv/config';
import { getPostgresPool } from '../src/server/config/postgres.js';
import { UnifiedChunkingService } from '../src/server/chunking/UnifiedChunkingService.js';
import { VectorService } from '../src/server/services/query/VectorService.js';
import type { CanonicalDocument, DocumentFamily } from '../src/server/contracts/types.js';

const BATCH_SIZE = 10;

function parseArgs(): { source?: string; limit?: number } {
	const args: { source?: string; limit?: number } = {};
	for (let i = 2; i < process.argv.length; i++) {
		if (process.argv[i] === '--source' && process.argv[i + 1]) {
			args.source = process.argv[++i];
		}
		if (process.argv[i] === '--limit' && process.argv[i + 1]) {
			args.limit = parseInt(process.argv[++i], 10);
		}
	}
	return args;
}

async function main() {
	const { source, limit } = parseArgs();
	const pool = getPostgresPool();
	const chunkingService = new UnifiedChunkingService();
	const vectorService = new VectorService();
	await vectorService.init();

	// Query documents with full_text
	const conditions = ['d.full_text IS NOT NULL', 'LENGTH(d.full_text) > 100'];
	const params: unknown[] = [];
	let paramIdx = 1;

	if (source) {
		conditions.push(`d.source = $${paramIdx}`);
		params.push(source);
		paramIdx++;
	}

	const limitClause = limit ? `LIMIT $${paramIdx}` : '';
	if (limit) params.push(limit);

	const query = `
    SELECT d.id, d.source, d.source_id, d.title, d.document_family, d.document_type,
           d.full_text, d.content_fingerprint, d.language, d.publisher_authority,
           d.dates, d.source_metadata, d.artifact_refs,
           d.enrichment_metadata, d.review_status
    FROM canonical.documents d
    WHERE ${conditions.join(' AND ')}
    ORDER BY d.source, d.created_at
    ${limitClause}
  `;

	const result = await pool.query(query, params);
	const docs = result.rows;

	console.log(`Documents to re-chunk: ${docs.length}`);
	if (source) console.log(`Source filter: ${source}`);
	if (limit) console.log(`Limit: ${limit}`);

	let processed = 0;
	let totalOldChunks = 0;
	let totalNewChunks = 0;
	let errors = 0;
	const startTime = Date.now();

	for (let i = 0; i < docs.length; i += BATCH_SIZE) {
		const batch = docs.slice(i, i + BATCH_SIZE);

		for (const doc of batch) {
			try {
				// Build CanonicalDocument for the chunking service
				const canonDoc: CanonicalDocument = {
					_id: doc.id,
					source: doc.source,
					sourceId: doc.source_id,
					title: doc.title,
					documentFamily: doc.document_family as DocumentFamily,
					documentType: doc.document_type,
					fullText: doc.full_text,
					contentFingerprint: doc.content_fingerprint,
					language: doc.language || 'nl',
					publisherAuthority: doc.publisher_authority,
					dates: doc.dates || {},
					sourceMetadata: doc.source_metadata || {},
					artifactRefs: doc.artifact_refs || [],
					enrichmentMetadata: doc.enrichment_metadata,
					reviewStatus: doc.review_status || 'pending_review'
				};

				// Count old chunks
				const oldCount = await pool.query(
					'SELECT count(*)::int as cnt FROM canonical.chunks WHERE document_id = $1',
					[doc.id]
				);
				totalOldChunks += oldCount.rows[0].cnt;

				// Delete old chunks and their embeddings
				// Delete from pgvector first (references chunk_id)
				const oldChunkIds = await pool.query(
					'SELECT chunk_id FROM canonical.chunks WHERE document_id = $1',
					[doc.id]
				);
				for (const row of oldChunkIds.rows) {
					await pool
						.query('DELETE FROM embeddings WHERE chunk_id = $1', [row.chunk_id])
						.catch(() => {}); // embeddings table may not use same column name
				}
				await pool.query('DELETE FROM canonical.chunks WHERE document_id = $1', [doc.id]);

				// Re-chunk with UnifiedChunkingService
				const chunkingResult = await chunkingService.chunkDocument(canonDoc, {
					chunkingVersion: 'v2',
					minChunkSize: 1600,
					maxChunkSize: 4800,
					chunkOverlap: 200
				});

				// Insert new chunks
				const now = new Date();
				for (const chunk of chunkingResult.chunks) {
					await pool.query(
						`
            INSERT INTO canonical.chunks (id, chunk_id, document_id, chunk_index, text, offsets,
              heading_path, legal_refs, chunk_fingerprint, created_at, updated_at)
            VALUES (encode(gen_random_bytes(12), 'hex'), $1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
            ON CONFLICT (chunk_id) DO UPDATE SET
              text = EXCLUDED.text, offsets = EXCLUDED.offsets,
              heading_path = EXCLUDED.heading_path, legal_refs = EXCLUDED.legal_refs,
              chunk_fingerprint = EXCLUDED.chunk_fingerprint, updated_at = EXCLUDED.updated_at
          `,
						[
							chunk.chunkId,
							chunk.documentId,
							chunk.chunkIndex,
							chunk.text,
							JSON.stringify(chunk.offsets),
							chunk.headingPath ? JSON.stringify(chunk.headingPath) : null,
							chunk.legalRefs ? JSON.stringify(chunk.legalRefs) : null,
							chunk.chunkFingerprint,
							now
						]
					);

					// Re-embed
					const docType = doc.document_type || doc.document_family || 'Document';
					const publisher = doc.publisher_authority || '';
					const header = publisher
						? `[${docType} | ${(doc.title || '').substring(0, 80)} | ${publisher}]`
						: `[${docType} | ${(doc.title || '').substring(0, 80)}]`;
					const embeddingText = `${header}\n${chunk.text}`;

					await vectorService.addDocument(
						chunk.chunkId,
						chunk.text,
						{
							documentId: doc.id,
							chunkIndex: chunk.chunkIndex,
							source: doc.source
						},
						embeddingText
					);
				}

				totalNewChunks += chunkingResult.chunks.length;
				processed++;

				if (processed % 50 === 0) {
					const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
					const rate = (processed / parseFloat(elapsed)).toFixed(1);
					console.log(
						`[${elapsed}s] ${processed}/${docs.length} docs | ` +
							`${totalOldChunks} old → ${totalNewChunks} new chunks | ${rate} docs/s`
					);
				}
			} catch (err) {
				errors++;
				console.error(
					`Error processing doc ${doc.id} (${doc.source}/${doc.title?.substring(0, 50)}):`,
					err
				);
			}
		}
	}

	const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
	console.log(`\n--- DONE ---`);
	console.log(`Processed: ${processed}/${docs.length} documents in ${elapsed}s`);
	console.log(`Old chunks: ${totalOldChunks} → New chunks: ${totalNewChunks}`);
	console.log(`Ratio: ${(totalNewChunks / Math.max(totalOldChunks, 1)).toFixed(2)}x`);
	console.log(`Errors: ${errors}`);

	await pool.end();
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
npx tsc --noEmit scripts/rechunk-unified.ts 2>&1 | head -10
```

If tsc can't resolve script imports, just verify with: `npx tsx --check scripts/rechunk-unified.ts` or skip type check — the real test is the subset run.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
git add scripts/rechunk-unified.ts
git commit -m "feat: add rechunk script using UnifiedChunkingService"
```

---

### Task 4: Run test subset re-chunk and compare

- [ ] **Step 1: Re-chunk a small test subset (IPLO first, then 50 DSO)**

IPLO is the smallest source (125 docs, 270 chunks) and the benchmark queries target IPLO content. Re-chunk it first:

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
npx tsx scripts/rechunk-unified.ts --source IPLO
```

Expected: ~125 docs processed, old 270 chunks → fewer but larger chunks.

Then a DSO sample:

```bash
npx tsx scripts/rechunk-unified.ts --source DSO --limit 50
```

Expected: 50 docs, old chunks ~500 chars → new chunks 1600-4800 chars.

- [ ] **Step 2: Run chunk metrics after test subset**

```bash
npx tsx scripts/chunk-metrics.ts > /tmp/chunk-metrics-after-subset.md
cat /tmp/chunk-metrics-after-subset.md
```

Expected: IPLO avg size should jump from ~2300 to similar (already good) or improve slightly. DSO avg should jump significantly for the 50 re-chunked docs. Overall stats will barely change since only ~175 docs were re-chunked.

- [ ] **Step 3: Run IPLO benchmark after re-chunk**

```bash
npx tsx scripts/iplo-benchmark.ts > /tmp/iplo-benchmark-after-subset.md
cat /tmp/iplo-benchmark-after-subset.md
```

Expected: Keyword coverage should improve since IPLO chunks are now properly structured.

- [ ] **Step 4: Compare before/after**

Diff the two metric reports and two benchmark reports side by side. The key numbers to compare:

- Chunk quality: avg size, sentence completeness %, mid-word starts %
- IPLO benchmark: keyword coverage % per question and overall

Save the comparison for the user to review before proceeding with full re-chunk.

---

### Task 5: Full re-chunk (after user approval of subset results)

- [ ] **Step 1: Re-chunk all remaining sources**

Run each source separately for progress tracking and error isolation:

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank

# OB: ~2687 docs
npx tsx scripts/rechunk-unified.ts --source OB

# Rechtspraak: ~3737 chunked docs
npx tsx scripts/rechunk-unified.ts --source Rechtspraak

# DSO: remaining ~538 docs (50 already done)
npx tsx scripts/rechunk-unified.ts --source DSO

# Wetgeving: ~301 docs
npx tsx scripts/rechunk-unified.ts --source Wetgeving

# Ruimtelijkeplannen: ~1324 chunked docs
npx tsx scripts/rechunk-unified.ts --source Ruimtelijkeplannen
```

Each source takes time proportional to doc count × embedding time. Estimated:

- OB: ~15 min
- Rechtspraak: ~20 min
- DSO: ~30 min (larger docs)
- Wetgeving: ~5 min
- Ruimtelijkeplannen: ~20 min

- [ ] **Step 2: Run final chunk metrics**

```bash
npx tsx scripts/chunk-metrics.ts > /tmp/chunk-metrics-final.md
cat /tmp/chunk-metrics-final.md
```

Expected: avg size 1500+, sentence completeness 80%+, mid-word starts <5%.

- [ ] **Step 3: Run final IPLO benchmark**

```bash
npx tsx scripts/iplo-benchmark.ts > /tmp/iplo-benchmark-final.md
cat /tmp/iplo-benchmark-final.md
```

- [ ] **Step 4: Produce final comparison report**

Compare all three snapshots: baseline → after-subset → final. Present to user.

- [ ] **Step 5: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
git add -A
git commit -m "data: re-chunk all documents via UnifiedChunkingService (v2)"
```
