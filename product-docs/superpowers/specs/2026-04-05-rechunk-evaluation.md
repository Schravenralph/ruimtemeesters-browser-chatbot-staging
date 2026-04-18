# Re-chunk Evaluation: Replace Backfill Script with UnifiedChunkingService

## Problem

97.9% of document chunks (127k of 130k) were created by a simple backfill script that slices text at fixed 500-character boundaries with 50-char overlap. No sentence awareness, no paragraph boundaries, no structure detection. Chunks cut mid-word and mid-sentence.

A proper `UnifiedChunkingService` already exists with family-specific strategies (DSO article boundaries, legal section headers, policy paragraph splitting), 1600-4800 char range, and 200 char overlap. The ~270 IPLO chunks processed through it average 2309 chars. It was never run on the bulk data.

## Goal

Prove the `UnifiedChunkingService` produces better chunks than the backfill script, then re-chunk all documents through it. Measure improvement with automated metrics and a retrieval benchmark.

## Scope

- **In scope:** Evaluate current vs UnifiedChunkingService chunks, re-chunk all documents, re-embed
- **Out of scope:** New chunking algorithms, changes to the UnifiedChunkingService itself, retrieval pipeline changes

## Evaluation Design

### 1. Chunk Quality Metrics (automated, all chunks)

Measured before and after re-chunking:

| Metric                    | How                                                                                                                                                 | Why                                                 |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **Avg chunk size**        | `avg(length(text))`                                                                                                                                 | 500 → ~2000+ expected                               |
| **Size distribution**     | Histogram buckets (≤500, 501-1000, 1001-2000, 2001-5000, >5000)                                                                                     | Should shift from 98% ≤500 to majority in 1000-5000 |
| **Sentence completeness** | % of chunks where `text` ends with `.`, `!`, `?`, or `)` (after trim)                                                                               | Measures whether chunks end at natural boundaries   |
| **Mid-word cuts**         | % of chunks where `text` starts or ends mid-word (regex: starts with lowercase after non-space, or ends with letter before non-space in next chunk) | Should drop to ~0%                                  |
| **Chunk count**           | Total chunks per source                                                                                                                             | Fewer, larger chunks expected                       |

### 2. Retrieval Benchmark (IPLO Q&A, 5 questions)

Same 5 IPLO questions from the earlier benchmark. For each question:

1. Query the Databank's `/api/search?q=...&limit=5` endpoint
2. Concatenate the returned chunk texts
3. Score: does the concatenated context contain enough information to answer the IPLO reference question?

Scoring per question (0-3):

- **0** = No relevant content in retrieved chunks
- **1** = Some relevant keywords/fragments but not enough to answer
- **2** = Partial answer possible — key facts present but incomplete
- **3** = Full answer possible — all key facts from the IPLO reference answer are present

The 5 test questions (from the earlier IPLO benchmark):

| #   | Question                                                             | IPLO Reference Answer (summary)                                                                                                                          |
| --- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Kan een gemeente de werkingssfeer van de bruidsschatregels wijzigen? | Ja, per locatie/regel laten vervallen, noemer + geometrisch informatieobject, moet voldoen aan Bkl hfst 5                                                |
| Q2  | Wijzigt de Vangnetregeling Omgevingswet de bruidsschat?              | Nee, ministeriële regeling die aanvult/verduidelijkt maar niet wijzigt, geen onderdeel omgevingsplan                                                     |
| Q3  | Wat regelt artikel 22.36, bruidsschat omgevingsplan?                 | Bijzondere gevallen bij Bor-omzetting: bijbehorend bouwwerk, erfafscheiding 1-2m, mantelzorg. Van rechtswege in overeenstemming bij naleving 22.27+22.36 |
| Q4  | Waar vind ik de bouwregels voor woningen?                            | Omgevingsplan (bouwhoogte, oppervlakte), Bbl (technische regels), BW (burenrecht)                                                                        |
| Q5  | Welke gebruiksregels gelden voor woningen?                           | Bruidsschat: geen overlast/hinder, bedrijf aan huis. Bbl: brandveiligheid. APV: openbare orde. BW: burenrecht                                            |

### 3. Execution Plan

**Phase 1: Baseline snapshot**

- Record all chunk quality metrics for current state
- Run IPLO benchmark, record scores
- Save results to a markdown report

**Phase 2: Re-chunk test subset**

- Pick ~100 documents per source (600 total) that have `full_text`
- Delete their existing chunks from `canonical.chunks`
- Re-chunk through `UnifiedChunkingService` with default config (1600-4800 chars)
- Re-embed with `Xenova/all-MiniLM-L6-v2`
- Record chunk quality metrics for the subset

**Phase 3: Run IPLO benchmark on re-chunked data**

- Run same 5 questions
- Score results
- Produce before/after comparison report

**Phase 4: Full re-chunk (if results are positive)**

- Write a production backfill script that:
  - Iterates all documents with `full_text`
  - Deletes old chunks for each document
  - Re-chunks via `UnifiedChunkingService`
  - Re-embeds via `VectorService`
  - Logs progress
- Run on all ~8100 documents with text
- No backward compatibility needed (confirmed by user)

**Phase 5: Final benchmark**

- Re-run all metrics and IPLO benchmark
- Produce final comparison report

## Technical Details

### Re-chunk Script

New script: `scripts/rechunk-with-unified-service.ts`

Uses existing services:

- `UnifiedChunkingService` for chunking (already has all strategies)
- `CanonicalChunkService.upsertChunks()` for storage
- `VectorService.addDocument()` for embeddings
- `LocalEmbeddingProvider` with `Xenova/all-MiniLM-L6-v2` (local, no API costs)

The script should:

1. Query documents with `full_text IS NOT NULL`
2. For each document: build a `CanonicalDocument` object, call `chunkDocument()`, upsert chunks, embed
3. Delete old chunks for documents being re-processed (chunks table uses `document_id` FK)
4. Process in batches of 20 for memory management
5. Log: documents processed, chunks created, errors, timing

### Embedding Considerations

- Local model, ~100ms per chunk → 130k chunks ≈ 3.6 hours
- Can be parallelized (VectorService supports batch operations)
- Re-embedding is required because chunk IDs and content change
- Old embeddings for deleted chunks should be cleaned up from pgvector

## Success Criteria

- Chunk quality metrics show clear improvement (avg size 4x+, sentence completeness 90%+, mid-word cuts <1%)
- IPLO benchmark score improves from current 4/15 to 8+/15
- No documents lose chunks (every doc with `full_text` should still have chunks after re-processing)
- Full re-chunk completes without errors on all sources
