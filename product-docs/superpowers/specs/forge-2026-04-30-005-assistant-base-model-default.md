---
forge_cycle: 5
date: 2026-04-30
size: small
---

# Forge Spec: Assistant base-model defaults to hosted Gemini

## What

`rm-tools/register_assistants.py`:

1. Change `BASE_MODEL` default from `'llama3.1:latest'` to
   `'gemini.gemini-2.5-flash-lite'` — matches the `DEFAULT_MODELS`
   already set in `docker-compose.rm.yaml` for new chats.
2. Add a `--base-model` CLI flag so self-hosted deployments without
   Gemini wired up can override it (e.g. `--base-model llama3.1:latest`).
3. Surface the chosen model in `--dry-run` output.

## Why

The 5 RM assistants today inherit from a **local Ollama** model
(`llama3.1:latest`). On `chatbot.datameesters.nl`:

- New chats default to `gemini.gemini-2.5-flash-lite` (hosted, fast,
  cheap, verified working) per brand-pass-2 § 4.
- But clicking any specialist assistant — Beleidsadviseur, Demografie
  Analist, Ruimtelijk Adviseur, Sales Adviseur, **or even Ruimtemeesters
  Assistent** — falls back to `llama3.1:latest`.
- If Ollama is unhealthy, paused, or doesn't have llama3.1 pulled,
  every specialist assistant 500s. The advisor sees a clean error in
  the chat surface but has to switch to the model picker manually.

Aligning the assistant base-model with the chat default fixes this
resilience gap. Self-hosted deployments without Gemini still have an
escape hatch via `--base-model`.

## Success criteria

1. `--dry-run` reports `base_model_id: gemini.gemini-2.5-flash-lite`
   for all 5 assistants by default.
2. `--base-model llama3.1:latest` overrides for all 5 assistants.
3. `5/5 + 12/12` totals unchanged.
4. `python3 -m py_compile` passes.
5. The script's docstring usage block mentions `--base-model`.

## Approach

- Replace the global `BASE_MODEL = ...` constant with a function
  parameter on `register_model` / `dry_run_model`. Each ASSISTANT entry
  keeps `'base_model_id': BASE_MODEL` as a default placeholder, but the
  CLI sets the actual value at runtime via `--base-model`.
- Backward-compatible: the dict-level `base_model_id` is overridden
  only when the CLI flag is set (otherwise we keep the dict's default,
  which we'll set to the new Gemini default).
- Keep the constant for clarity at the top of the file with a comment
  pointing at the CLI override.

## Not doing

- A per-assistant override (e.g., one assistant on Opus, another on
  Flash Lite). Not needed today — uniform default + global CLI override
  is enough.
- Validating that the chosen base model is actually registered in the
  target OpenWebUI. The model creation endpoint will return a clean
  error if it isn't, which is fine.
- Updating the 5 assistant SVG icons or system prompts.
