# Forge Spec: Ship ADR-0011 3-persona canon in register_assistants.py

**Cycle:** 1 | **Clock:** ~0h elapsed | **Size:** medium

## What

Replace the 5 deprecated assistant registrations in `rm-tools/register_assistants.py` (Beleidsadviseur, Demografie Analist, Ruimtelijk Adviseur, Sales Adviseur, Ruimtemeesters Assistent) with the 3 canonical personas (RO Assistent, Juridisch Assistent, Commercieel Assistent) per Platform ADR-0011. System prompts, tool curation, and slugs are sourced from `product-docs/25-assistants/{ro-assistent,juridisch-assistent,commercieel-assistent}.md` which already document the canon.

## Why

ADR-0011 (Accepted) defines the canon. `product-docs/25-assistants/` already ships the three canonical docs. But `register_assistants.py` — the script that actually creates the OpenWebUI models users see in the chatbot — still ships the deprecated 5. Result: the canon is documented but not deployed; advisors see "Sales Adviseur" instead of "Commercieel Assistent", and there is no Juridisch Assistent at all. This blocks every persona-skill binding decision downstream (incl. cycle 2's Commercieel skill and cycle 3's Scanmethode manifest, both of which target canonical slugs).

## Success criteria

1. `rm-tools/register_assistants.py` registers exactly 3 models with names matching ADR-0011 (`RO Assistent`, `Juridisch Assistent`, `Commercieel Assistent`) and ids `rm-ro-assistent` / `rm-juridisch-assistent` / `rm-commercieel-assistent`.
2. Each persona's `toolIds` matches the product-docs spec (RO → geoportaal/databank/aggregator/tsa/dashboarding/memory; Juridisch → databank/nieuws/memory; Commercieel → riens/opdrachten/sales-predictor/memory).
3. The BOPA workflow guidance + memory recall/save guidance currently in `rm-assistent`'s system prompt is preserved on the RO Assistent (where it belongs).
4. Slash-command PROMPTS list unchanged (they're persona-agnostic).
5. `python rm-tools/register_assistants.py --dry-run` succeeds and prints the 3 expected payloads.

## Approach

- Direct rewrite of the `ASSISTANTS` list. The product-docs system prompts are the contract; copy them in.
- Preserve all non-persona content (PROMPTS, FILTERS, helper functions).
- Bind filters (`bopa_session_context`, `memory_recall_context`, `memory_save_prompt`) to all 3 personas — every persona benefits from session-context priming and memory recall.
- Profile images: RO → map-pin, Juridisch → policy, Commercieel → currency.

## Not doing

- Not changing `PROMPTS` (slash commands).
- Not changing `FILTERS` definitions.
- Not building new MCP servers — only bind to currently-running ones (no `rm-wetten`, no `rm-document-generator`, no `rm-crm`, no `rm-mailchimp` — those don't exist yet).
- Not touching `product-docs/25-assistants/` — those already match the canon.
- Not editing LiteLLM routing config — the model id is the routing key; updated ids implicitly migrate that side.
