# Databank Document Chunks Are Too Small and Cut Mid-Sentence

**Date:** 2026-04-05
**Severity:** high
**Service:** Ruimtemeesters-Databank
**Phase found:** benchmark

## Description

The Databank's document chunks are ~500 characters, often cutting mid-sentence. In IPLO benchmark testing (5 questions from iplo.nl FAQ), the retrieved chunks contained fragments of legal text that couldn't be used to construct coherent answers.

Example: a chunk about artikel 22.1 cut off at "...de bekendmaking van het bestemmingsplan of inpassing" — the rest of the sentence (with the actual rule) is in the next chunk.

## Impact

This is the #1 blocker for chatbot answer quality. Even with correct document retrieval (the right documents are found), the content chunks are too small and fragmented to synthesize answers. IPLO benchmark: 0/5 full answers, 2/5 partial, 3/5 fail.

## Fix

See plan: `product-docs/superpowers/plans/2026-04-05-aggregator-kg-proxy-and-chunking.md` (chunking section).

Needs evaluation of chunking strategies with before/after metrics. Key changes:

- Increase chunk size to 1500-2000 chars
- Never split mid-sentence
- Split on logical boundaries (paragraph, article, section heading)
- Add 200 char overlap between chunks
- Source-specific splitting (IPLO: section headers; DSO: article boundaries; OB: paragraph breaks)
