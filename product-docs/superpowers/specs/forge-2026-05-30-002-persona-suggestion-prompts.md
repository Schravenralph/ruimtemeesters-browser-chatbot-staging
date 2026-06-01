# Forge Spec: Persona-specific empty-chat suggestion prompts

**Cycle:** 4 | **Size:** small

## What

Populate `suggestion_prompts: []` for all three personas (RO, Juridisch,
Commercieel) in `scripts/personas.yaml` with 4 starter prompts each.
The infrastructure to render them is already shipped — `ChatPlaceholder`
reads `model.info.meta.suggestion_prompts` and `Suggestions.svelte`
renders the cards. Today the array is empty for every persona.

## Why

The empty-chat state is the first thing every advisor sees on a fresh
chat. Currently it's blank — they get the model selector + a search
bar but no concrete prompts pointing at the workflows the persona is
actually built for. Worse: a Commercieel advisor lands on the
Commercieel-Assistent and sees no signal that opdrachten-scan or
gemeente-snapshot are available.

Persona-specific starters:

- **Anchor the advisor to that persona's job** — RO sees BOPA /
  beleidsscan / locatiescan; Juridisch sees citation / onderbouwing;
  Commercieel sees opdrachten / acquisitie.
- **Surface skills shipped in PR #151 + the on-demand MCP lane** — a
  "Beleidsscan starten" card calls the same skill the filter loads,
  making the connection obvious instead of magical.
- **Reduce blank-page friction** for new advisors during onboarding.

## Success criteria

1. Each persona ships 4 suggestion prompts.
2. Re-running `scripts/seed_personas.py` loads the new prompts into the
   `model.info.meta.suggestion_prompts` for each persona row in OWUI.
3. Loading the chat home with RO, Juridisch, or Commercieel selected
   renders the 4 cards (one per persona).
4. Clicking a card inserts the prompt into the composer.

## Approach

- Pure YAML edit. The `SuggestionPrompt` schema in
  `scripts/personas_schema.py` is `{content: str, title: list[str]}`,
  rendered as `title[0]` (bold) + `title[1]` (subtitle) over a click
  target whose payload is `content`.
- Match the advisor language used in the persona system prompts
  (Nederlands), not English UI copy.
- Reference the actual skills + tools each persona has — don't promise
  workflows that aren't wired.

## Not doing

- Per-user customisation of starter prompts (out of scope; user
  settings already let people add their own).
- A/B testing or telemetry — measure later when there's signal.
- Internationalisation of the prompts (NL only; matches the persona
  system prompts).
