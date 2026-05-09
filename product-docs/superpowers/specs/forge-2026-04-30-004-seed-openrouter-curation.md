---
forge_cycle: 4
date: 2026-04-30
size: small
---

# Forge Spec: Extend `seed-gemini-connection.sh` to also seed OpenRouter

## What

Update `scripts/seed-gemini-connection.sh` so that running it on a fresh
DB persists the curation for **all three** OpenAI-compatible connections
declared in `docker-compose.rm.yaml` — OpenAI (placeholder), Gemini, and
OpenRouter — instead of just the first two.

## Why

`b3b556cbb` ("feat: add OpenRouter as 3rd LLM connection") extended
`OPENAI_API_BASE_URLS` and `OPENAI_API_KEYS` to three entries in compose
but left the seed script writing only two. After any `docker compose
down -v` followed by re-seeding:

- The script POSTs `OPENAI_API_BASE_URLS=[OpenAI, Gemini]` to
  `/openai/config/update`.
- The DB `config` row now persists exactly two entries.
- Per the OpenWebUI foot-gun "PersistentConfig: env reads only on first
  boot, DB wins after", the OpenRouter entry never comes back from the
  env on subsequent restarts.
- Result: Claude Opus 4.7 / DeepSeek / Llama / etc. silently disappear
  from the model picker until an admin manually re-adds OpenRouter via
  the UI.

The script is the documented recovery path (brand-pass-2 spec § 9 +
foot-guns memory). It must be a complete restore, not a partial one.

## Success criteria

1. The script writes a 3-entry `OPENAI_API_BASE_URLS` and 3-entry
   `OPENAI_API_KEYS` (positions 0/1/2 = OpenAI/Gemini/OpenRouter).
2. `OPENAI_API_CONFIGS["2"]` carries `prefix_id="openrouter"`,
   `tags=[{name: "OpenRouter"}]`, and a curated `model_ids` list of at
   least 3 entries covering Claude (Anthropic) + at least one
   non-Anthropic provider (DeepSeek / Llama / Qwen / etc.).
3. The script gracefully handles a missing `OPENROUTER_API_KEY`: warn,
   skip the OpenRouter slot, but still seed Gemini.
4. `bash -n scripts/seed-gemini-connection.sh` (syntax check) passes.
5. The post-POST sanity check verifies both Gemini (5 models) and
   OpenRouter (≥3 models) when the OpenRouter key is present.

## Approach

- Extract `OPENROUTER_KEY` via the same container-env read pattern
  already used for Gemini (position 2 of the `;`-split list).
- Branch on `OPENROUTER_KEY` empty vs present:
  - **Empty:** keep the existing 2-entry body unchanged (back-compat).
  - **Present:** build a 3-entry body, append the OpenRouter config
    slot.
- OpenRouter `model_ids` curation — start small and stable:
  - `anthropic/claude-opus-4.7` (headline)
  - `anthropic/claude-sonnet-4.6`
  - `anthropic/claude-haiku-4.5`
  - `deepseek/deepseek-r1`
  - `meta-llama/llama-3.3-70b-instruct`

  Unknown IDs get silently filtered by the picker — not a blocker, just
  fewer visible models. Admins can adjust later.

- Update the docstring at the top of the script to say
  "Gemini + OpenRouter" instead of "Gemini".
- Update the post-POST sanity check to count both lists.

## Not doing

- Renaming the script. `measure-brand.sh:39` and the brand-pass-2 spec
  reference it by name — a rename would force a churn-y multi-file PR.
  Docstring update is enough.
- Cleaning up the duplicate `GEMINI_API_KEY=` declaration in
  `.env.rm.example` (cosmetic; orthogonal cycle).
- Adding new OpenRouter integrations (auth, billing dashboards, etc.)
- Validating OpenRouter model IDs against `https://openrouter.ai/api/v1/models`
  (network-dependent; if an ID is wrong, the picker just hides it).
