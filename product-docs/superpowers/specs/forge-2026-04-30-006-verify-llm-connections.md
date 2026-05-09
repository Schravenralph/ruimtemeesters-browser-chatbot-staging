# Spec — `scripts/verify-llm-connections.sh` (post-deploy LLM curation check)

**Date:** 2026-04-30
**Status:** Approved (forge cycle, backlog #3 from 2026-04-30 forge report)
**Repo:** `Ruimtemeesters-Browser-Chatbot`
**Depends on:** `scripts/seed-gemini-connection.sh` (cycle 4) — already merged.

## 1. Goal

Cycle 4 fixed `seed-gemini-connection.sh` so it writes the full
3-connection shape (OpenAI placeholder / Gemini / OpenRouter) that
matches `docker-compose.rm.yaml`. There is no asserting equivalent yet:
nothing fails CI or post-deploy if the persisted DB drifts back to
2 entries, or if the curated `model_ids` list was edited away under the
admin UI.

This spec ships `scripts/verify-llm-connections.sh` — a JSON-emitting
post-deploy check, parallel to `scripts/measure-brand.sh`, that asserts
the resulting OpenWebUI `OPENAI_API_*` config matches the curation we
expect.

## 2. Non-goals

- Not a CI gate yet — same as `measure-brand.sh` it's a tool the operator
  runs after deploy or seed; wiring it into CI is a follow-up
- Not a fixer — it verifies, it doesn't re-seed (seed script does that)
- Not Ollama-specific — the connection list it checks is the
  OpenAI-compatible list (`/openai/config`); Ollama's separate config
  endpoint is out of scope

## 3. Behavior

### Inputs (overridable env)

```
HOST=http://localhost:3333
APP_CONTAINER=rm-chatbot
DB_CONTAINER=rm-chatbot-db
ADMIN_USER_ID=<auto-resolved from DB>
EXPECT_OPENROUTER=auto   # auto | yes | no
```

`EXPECT_OPENROUTER=auto` checks the container env: if
`OPENROUTER_API_KEY` is non-empty, expect 3 connections; else expect 2.
Operators can force a check with `yes`/`no` in CI/post-deploy.

### Output

A single JSON object on stdout, mirroring `measure-brand.sh`:

```json
{
  "timestamp": "2026-04-30T...",
  "host": "http://localhost:3333",
  "expect_openrouter": true,
  "criteria": {
    "A_openai_api_enabled": { "value": true, "pass": true },
    "B_base_urls_count": { "value": 3, "expected": 3, "pass": true },
    "C_gemini_connection": {
      "prefix_id": "gemini",
      "enabled": true,
      "model_count": 5,
      "model_ids": [...],
      "pass": true
    },
    "D_openrouter_connection": {
      "prefix_id": "openrouter",
      "enabled": true,
      "model_count": 5,
      "model_ids": [...],
      "pass": true
    },
    "E_openai_placeholder_disabled": {
      "url": "https://api.openai.com/v1",
      "enabled": false,
      "pass": true
    }
  },
  "all_pass": true
}
```

Exit code: `0` if every criterion passes, `1` otherwise. Stderr stays
silent on success, prints a one-line summary on failure.

### Pass thresholds per criterion

| ID  | Criterion                       | Pass when                                                                                |
| --- | ------------------------------- | ---------------------------------------------------------------------------------------- |
| A   | `ENABLE_OPENAI_API` is true     | exact `True`                                                                             |
| B   | Number of base URLs             | `==3` when `expect_openrouter=true`, `==2` when `false`                                  |
| C   | Gemini connection (idx `1`)     | `prefix_id=='gemini'`, `enable==true`, `model_ids` length `==5`                          |
| D   | OpenRouter connection (idx `2`) | only when `expect_openrouter`: `prefix_id=='openrouter'`, `enable==true`, `≥3` model ids |
| E   | OpenAI placeholder (idx `0`)    | base URL is `https://api.openai.com/v1`, `enable==false`                                 |

The thresholds match what `seed-gemini-connection.sh` writes today.

## 4. Implementation plan

1. New `scripts/verify-llm-connections.sh`, executable.
2. Reuses three idioms from `seed-gemini-connection.sh` and `measure-brand.sh`:
   - `ADMIN_USER_ID` resolved from DB if not provided
   - Admin JWT minted inside the app container via `create_token` + `WEBUI_SECRET_KEY`
   - JSON parsing in inline `python3 -c`, env-var-passed input (no shell interpolation of secrets)
3. `GET /openai/config` returns the same shape `seed-gemini-connection.sh` POSTs.
4. Python validator block emits the JSON above and exits non-zero on any criterion failure.

## 5. Success criteria

| Criterion                                                                                                                   | Threshold                | How measured                                                                             |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| Script exists and is executable                                                                                             | yes                      | `[ -x scripts/verify-llm-connections.sh ]`                                               |
| Bash syntax check                                                                                                           | pass                     | `bash -n scripts/verify-llm-connections.sh`                                              |
| Run against a freshly-seeded local stack (3 connections)                                                                    | `all_pass=true`          | `scripts/seed-gemini-connection.sh && scripts/verify-llm-connections.sh \| jq .all_pass` |
| Stale-shape detection — manually POST a 2-entry config to `/openai/config/update`, then re-run with `EXPECT_OPENROUTER=yes` | `all_pass=false`, exit 1 | regression check                                                                         |
| Documented in `scripts/seed-gemini-connection.sh` header (one-liner pointer)                                                | yes                      | header mentions `verify-llm-connections.sh`                                              |

## 6. Validation

1. **Lint:** `bash -n scripts/verify-llm-connections.sh`
2. **Happy path:** With local stack running and seeded:
   ```bash
   scripts/verify-llm-connections.sh | jq -r '.all_pass'
   # → true
   ```
3. **Regression path:** Manually clobber the config to 2 entries, re-run:
   ```bash
   # forces a 2-entry config via curl, then:
   EXPECT_OPENROUTER=yes scripts/verify-llm-connections.sh
   echo $?  # → 1
   ```
4. **No-OpenRouter path:** With `OPENROUTER_API_KEY=""` in `.env`, recreate
   the container, re-seed, re-verify:
   ```bash
   scripts/verify-llm-connections.sh | jq -r '.all_pass, .expect_openrouter'
   # → true, false
   ```

## 7. Follow-ups

1. Wire `verify-llm-connections.sh` into the post-deploy hook (alongside
   `measure-brand.sh`) once both exist as a stable pair.
2. Symmetric script for Ollama's internal connection list when the seed
   for Ollama becomes worth automating.
