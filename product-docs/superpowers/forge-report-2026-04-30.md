# Forge Report — 2026-04-30

**Wall clock:** ~1.0h (57 min)
**Cycles completed:** 6 (1 chore + 5 features)
**Features shipped:** 6 merged, 0 pending review

## Shipped Features

| #   | Feature                                                       | PR  | Status | Time | Size  |
| --- | ------------------------------------------------------------- | --- | ------ | ---- | ----- |
| 0   | gitignore `.claude/worktrees/`                                | #25 | merged | ~3m  | XS    |
| 1   | BOPA slash prompts (`/bopa-haalbaarheid` x 3) + `--dry-run`   | #26 | merged | ~12m | small |
| 2   | Surface BOPA on `rm-assistent` (5th starter + system prompt)  | #27 | merged | ~6m  | small |
| 3   | `/bopa-status` slash prompt (session continuity)              | #28 | merged | ~5m  | small |
| 4   | Seed OpenRouter alongside Gemini (3rd connection survives DB) | #29 | merged | ~15m | small |
| 5   | Assistant `BASE_MODEL` defaults to hosted Gemini Flash Lite   | #30 | merged | ~6m  | small |

## Impact

### New use cases enabled

- **Discoverable BOPA workflow on `chat.datameesters.nl`** — an advisor opening
  Ruimtemeesters Assistent can now see and start a BOPA evaluation from the
  starter cards or the slash command palette. Before today the workflow was
  reachable only by typing the right English question.
- **`/bopa-status` continuity** — advisors returning after a few days have a
  one-touch lookup of their active BOPA sessions, including next logical phase
  and blocking dependencies.

### Existing UX enriched

- **5 specialist assistants stay online when Ollama is unhealthy** — the
  base-model now matches the chat-default Gemini Flash Lite, so a paused or
  un-pulled Ollama no longer 500s every specialist surface.
- **System prompt on `rm-assistent` names every wired tool** — `rm-memory` and
  Aggregator were silently in `toolIds` but invisible to the model; now
  surfaced with one line each. The BOPA-workflow paragraph names the three
  slash commands.

### Infrastructure expanded

- **`seed-gemini-connection.sh` is now multi-connection-aware** — restoring
  the LLM curation post-`docker compose down -v` no longer clobbers
  OpenRouter from the persisted DB. Documents the 3-entry shape that matches
  the compose. Graceful degradation when `OPENROUTER_API_KEY` is absent
  (back-compat).
- **`register_assistants.py` has `--dry-run` and `--base-model`** — local CI
  sanity checks no longer need a live admin token, and self-hosted
  deployments can override the base model per-environment.
- **`.gitignore` now covers `.claude/worktrees/`** — agent scratch trees no
  longer pollute `git status`.

## Bot review trail

- **Bugbot findings**: 2 issues across all 6 PRs (PR #26: Phase 3
  prerequisite-fallback consistency + dry-run/register payload duplication).
  Both fixed in the same PR before merge. Subsequent re-reviews flagged 0
  issues on the fix commits — the persisted comment positions are stale
  re-anchors that GitHub repositions when the file changes.
- **Format CI**: 1 round of prettier reflow on a spec markdown sub-list (PR
  #29). Fixed by running `prettier --write` locally.

## Unfinished / Next Session

| Priority | Feature                                                                                                    | Why                                                                                                                                                                                                                                              | Est. size |
| -------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| 1        | OpenWebUI inlet filter to auto-inject active BOPA session summary (BOPA spec §6 follow-up #4)              | Closes the loop on cycles 1–3: advisors with an active BOPA session would land in any new chat with the session state already in the system prompt, no explicit tool call needed. Touches OpenWebUI's filter framework — cycle, not micro-cycle. | M         |
| 2        | Skill-sync mechanism between `packages/memory/skills/bopa.md` and `.claude/skills/bopa/SKILL.md`           | Currently a manual copy. A small CI check or sync script prevents drift across the two repos.                                                                                                                                                    | S         |
| 3        | `scripts/verify-llm-connections.sh` parallel to `measure-brand.sh`                                         | Cycle 4 fixed the seed; this would assert the resulting DB state (3 connections, prefix_ids, model_ids). Repeatable post-deploy check.                                                                                                           | S         |
| 4        | Phase 4–6 BOPA slash prompts (`/bopa-omgevingsaspecten`, `/bopa-onderbouwing`, `/bopa-toetsing`)           | Blocked on matching MCP tools landing in the memory package. Re-evaluate once `Ruimtemeesters-MCP-Servers` ships them.                                                                                                                           | XS each   |
| 5        | Close stale issue files: `2026-04-17-audit-whitelist-never-matches.md` (compose value already correct)     | Cycle 0-style cleanup; one paragraph per file.                                                                                                                                                                                                   | XS        |
| 6        | Specialist-assistant consolidation into `rm-assistent` per single-agent policy (BOPA spec §6 follow-up #1) | Larger; touches all 5 assistants. Best done as one explicit migration session, not a forge cycle.                                                                                                                                                | L         |

## Stash to revisit (forge-pre)

`git stash list` shows `stash@{0}: forge-pre: test fixes (provider/redis), deleted upstream tests, lock drift`. The two test-side patches (`test_provider.py` GCS/Azure env bootstrap, `test_redis.py` `MAX_RETRY_COUNT` rename) look like genuine bug fixes worth a separate small PR. The 3 deleted upstream test files want investigation before commit. Lock-file drift can be regenerated.

## Observations

- **"BOPA-spec mining" was high-leverage**: cycles 1–3 all came from line-item
  follow-ups already approved in `2026-04-17-bopa-assistant-config.md`. When
  a spec lists explicit deferrals, those are the cleanest forge candidates —
  pre-validated, scoped, success-criteria already written.
- **Bugbot "found N issues" comments persist across commits**: even after a
  fix push, the original review's anchored comments re-position to the new
  HEAD. The new bugbot status check (`Cursor Bugbot: pass`) is the
  authoritative signal, not the comment count.
- **Cycle 4 surfaced a real production foot-gun**: `seed-gemini-connection.sh`
  silently writing a 2-entry `OPENAI_API_BASE_URLS` over a 3-entry compose
  state was an accident waiting to happen. That class of "config drift after
  feature add" probably exists for other persisted-config admin scripts —
  worth a sweep next session.
- **Drift signal hit at cycle 5**: third operational/admin cycle in a row
  with no obvious mid-sized fresh-area feature in this repo. Stopping was
  cheaper than forcing one.
