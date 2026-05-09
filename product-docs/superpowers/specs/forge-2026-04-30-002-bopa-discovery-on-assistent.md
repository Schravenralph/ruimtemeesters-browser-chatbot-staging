---
forge_cycle: 2
date: 2026-04-30
size: small
---

# Forge Spec: Surface BOPA on the general Ruimtemeesters Assistent

## What

On the `rm-assistent` (general agent) entry in `register_assistants.py`:

1. Add a BOPA-themed `suggestion_prompt` so a fresh chat session offers
   "Start een BOPA-haalbaarheidstoets" as a one-click starter card next
   to the existing four (luchtkwaliteit, bevolkingsprognose, contracten,
   opdrachten).
2. Update the system prompt to mention `rm-memory` (BOPA session state)
   alongside the other 8 MCP tools, with one line about the BOPA workflow
   and how to invoke it via `/bopa-haalbaarheid`.

## Why

PR #26 (cycle 1) shipped the slash commands. But a user opening
`chat.datameesters.nl` on **Ruimtemeesters Assistent** sees four starter
prompts — none of which hint at BOPA. Unless they already know the slash
exists, BOPA is invisible. Adding it as the 5th starter card surfaces the
new workflow at the top of the funnel.

The system-prompt update is explicitly called out in the BOPA spec
§ 3A: "Update its system prompt to mention memory alongside the other
tools." That part never landed in PR #22. Without it the model doesn't
know `rm-memory` exists by name and may not recognise BOPA-flavored
asks even with the tool wired in.

## Success criteria

1. `python3 rm-tools/register_assistants.py --dry-run` still reports
   `5/5 + 11/11`, and `rm-assistent` shows `suggestion_prompts: 5` (was 4).
2. The 5th suggestion's content references BOPA / haalbaarheidstoets.
3. The `rm-assistent` system prompt mentions `rm-memory` and the BOPA
   workflow, with at least one slash command name in the body.
4. `python3 -m py_compile` passes.

## Approach

- One Edit on `rm-tools/register_assistants.py`: append a 5th dict to
  `rm-assistent.meta.suggestion_prompts` and rewrite the system-prompt
  string (the `params.system` field) to include the new tool + workflow
  lines.
- No changes to the 4 specialist assistants — BOPA is a general-agent
  workflow per the single-agent policy.
- No changes to PROMPTS.

## Not doing

- Adding BOPA suggestion_prompts to the 4 specialist assistants
  (consolidating those is a separate follow-up per the BOPA spec § 6).
- A "tour" / first-run modal for the BOPA flow (UI change, out of scope
  for register_assistants.py).
- Any frontend work in OpenWebUI's Svelte tree.
