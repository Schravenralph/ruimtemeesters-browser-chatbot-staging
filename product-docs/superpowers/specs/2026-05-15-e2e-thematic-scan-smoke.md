# End-to-end smoke test: thematic policy scan

**Date:** 2026-05-15
**Status:** Draft (proactive-brainstorm Phase 3)
**Tracking:** Browser-Chatbot #108, Skills #11, MCP-Servers #98, Memory #28

## Goal

A scripted test that verifies the critical-path advisor flow works end-to-end after all four sibling specs ship:

> _Advisor opens RO Assistent, asks "doe een thematische beleidsscan voor gemeente Utrecht op thema energietransitie", and the model follows the 5-step canon from `skills/beleidsscan/SKILL.md` with project-scoped memory binding._

Lives in `Ruimtemeesters-Browser-Chatbot` because that's where the orchestration happens.

## Where it lives

`scripts/smoke/thematic_scan_smoke.sh` — bash + curl + jq. Self-contained, runnable against either local docker-compose stack or production with a flag.

```bash
./scripts/smoke/thematic_scan_smoke.sh --target=local
./scripts/smoke/thematic_scan_smoke.sh --target=prod  # requires WEBUI_TOKEN env
```

## What it verifies (4 stages, fail-fast)

### Stage 1 — Services reachable

- `curl ${API}/api/health` → 200
- `curl ${API}/api/v1/models` → contains `ro-assistent` (or `rm-assistent` in legacy)
- `curl ${SKILLS}/api/v1/skills?persona=ro-assistent` → returns at least `beleidsscan`
- `curl ${MEMORY_MCP}/health` → 200
- `curl ${SKILLS_MCP}/health` → 200

Fails if any service is down or the persona/model is missing.

### Stage 2 — Skill injection visible

- POST a chat-completions request to `${API}/api/chat/completions` with:
  - `model: ro-assistent`
  - `messages: [{role: "user", content: "doe een thematische beleidsscan voor gemeente Utrecht op thema energietransitie"}]`
  - Enable a debug header that causes the response to include the assembled system prompt (or query an admin debug endpoint)
- Assert: response system-prompt content contains `<skill name="beleidsscan">`
- Assert: skill body length > 8000 chars
- Assert: chat history persists (chat-id returned)

Fails if the `skills_context` filter didn't fire or rm-skills didn't return content.

### Stage 3 — Project binding

- The model SHOULD call `set_active_project({project_id: "beleidsscan:GM0344:energietransitie", kind: "beleidsscan"})` early in its flow (the `beleidsscan` SKILL.md instructs this)
- After the chat turn completes, query memory MCP directly:
  - `tools/call get_active_project` with the chat-id
  - Assert returned `project_id == "beleidsscan:GM0344:energietransitie"`

Fails if the model didn't follow the canon or the active-project tool isn't wired.

### Stage 4 — Output follows canon

- Inspect the assistant's response text
- Assert it references at least 4 of the 5 step markers from beleidsscan SKILL.md (extract markers in the smoke script at runtime by parsing the SKILL.md file)
- Assert the response is in Dutch (>90% Dutch tokens — cheap heuristic: count common Dutch words)
- Assert response length > 500 chars (not a refusal / one-liner)

Fails if the model improvised instead of following the canon.

## Success criteria (the smoke itself)

| #   | Criterion                                                              | How to measure                                                 |
| --- | ---------------------------------------------------------------------- | -------------------------------------------------------------- |
| E1  | All 4 stages pass against local docker-compose stack                   | Exit code 0                                                    |
| E2  | Smoke completes in < 90s end-to-end                                    | `time` output                                                  |
| E3  | Failure mode for each stage produces a clear diff (expected vs actual) | Manually break each component and run; verify error legibility |
| E4  | Runs on a fresh prod deploy without state pollution                    | Use a throwaway test user account; cleanup at end              |
| E5  | Idempotent: running 10x in a row passes each time                      | CI repeat                                                      |

## Validation plan

1. Run script with all 4 specs deployed locally → all stages pass.
2. **Break each component in turn** and assert correct stage fails:
   - Stop rm-skills → Stage 1 fails
   - Disable `skills_context` filter → Stage 2 fails (no skill block)
   - Mock model to not call `set_active_project` → Stage 3 fails
   - Mock model to give a 100-char reply → Stage 4 fails
3. Run against prod with a test user account; cleanup deletes test chats and active_project rows.

## Comparison to baseline

There is no baseline — this is a new test. The closest comparison:

| Today                                        | After this smoke                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| No end-to-end test for the advisor flow      | One scripted verification covering all 4 components                       |
| Regressions discovered only via user reports | Smoke runs on every prod deploy (manual trigger initially; CI hook later) |

## CI wiring (follow-up, not in v1)

- Add to a `make smoke` target locally
- Manual trigger only in v1 (per memory: no GitHub Actions for RM-owned concerns)
- Eventually: post-deploy hook in deploy script

## Risks & mitigations

- **R1 — Flaky LLM behaviour**: model is non-deterministic; "calls set_active_project" might not happen on every run. Mitigation: temperature-low test model, OR retry up to 3 times with assertion check after each.
- **R2 — Smoke creates real data in prod**: Mitigation: test user account with prefix `smoke-test-`; cleanup at end; daily pruner sweeps stale anyway.
- **R3 — Step-marker extraction fragile**: if SKILL.md changes wording, smoke breaks. Mitigation: extract markers from SKILL.md at runtime so smoke tracks canon edits automatically.

## Out of scope / follow-ups

- Playwright UI smoke (chat-UI rendering, not just API): worth a dedicated spec when chat UI changes risk regressions
- Smoke for Juridisch / Commercieel personas: same pattern, separate scripts
- Beleidsscan completeness (does the scan finish all 5 phases?): the smoke verifies the model _starts_ correctly, not that a full scan completes
