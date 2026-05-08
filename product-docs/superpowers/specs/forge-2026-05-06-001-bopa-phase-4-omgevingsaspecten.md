# Forge Spec: BOPA Phase 4 — /bopa-omgevingsaspecten slash prompt

**Cycle:** 1 | **Clock:** 0h elapsed | **Size:** medium

## What

Add a `/bopa-omgevingsaspecten` slash prompt to the chatbot so an advisor can run the BOPA Phase 4 (Omgevingsaspecten) toets from the chat. Update `/bopa-help` to drop the "Fase 4–6 niet gepubliceerd" caveat for Phase 4. Extend the BOPA inlet filter so when Phase 4 is the next-ready phase, the auto-injected hint suggests the new command.

## Why

`/bopa-help` tells advisors today: _"Fase 4–6 commando's zijn nog niet gepubliceerd (MCP-tools in de wacht)."_ That caveat is stale: `sample_bopa_constraints_at_point`, `theme_profile_for_gemeente`, and `rules_by_gemeente_and_theme` all exist on the geoportaal + databank MCPs. The slash prompt is the missing piece that lets an advisor run Phase 4 without dropping into raw tool-calls. Continues the BOPA pipeline that is the product's primary motion.

## Success criteria

1. `/bopa-omgevingsaspecten` registered in `PROMPTS` (visible via `register_assistants.py --dry-run`).
2. `/bopa-help` content no longer says Phase 4 is unpublished — only Phases 5 and 6 remain "in de wacht".
3. `PHASE_SLASH_COMMANDS` in `bopa_session_context.py` includes `4: '/bopa-omgevingsaspecten'`; the inlet filter's next-step hint emits it when `next_phase == 4`.
4. Existing `test_bopa_inlet_filter.py` still passes; one new test asserts the Phase-4 hint path.

## Approach

- Add prompt entry to `PROMPTS` mirroring the Phase 1-3 pattern: takes `{{session_id}}`, instructs the model to verify Phases 1+2+3 are complete (MCP rejects on unmet prereqs), call the three MCP tools, intersect spatial hits with regulated themas, and write back via `update_bopa_session({phase: 4, ...})`. Cite layer + article references, no uncited findings.
- Update `bopa-help` content string: drop "4" from the unpublished-phases sentence.
- Add `4: '/bopa-omgevingsaspecten'` to `PHASE_SLASH_COMMANDS` dict.
- Add a focused test in `test_bopa_inlet_filter.py` covering the Phase-4-next-step path. Don't write a test per phase — one test for the new path is the delta.

## Not doing

- Phase 5 / Phase 6 slash prompts — separate issues (#45 / #46), and they depend on MCP tools (#73 / #74) that don't exist yet.
- New MCP tools — Phase 4 backends already exist.
- Refactoring `PHASE_SLASH_COMMANDS` into a registry — keep the dict.
- Updating the BOPA skill in `.claude/skills/bopa/` — Claude-side guidance, separate concern.
