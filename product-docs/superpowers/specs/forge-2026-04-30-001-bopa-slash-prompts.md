---
forge_cycle: 1
date: 2026-04-30
size: small
---

# Forge Spec: BOPA slash prompts on the general assistant

## What

Add three BOPA slash prompts (`/bopa-haalbaarheid`, `/bopa-strijdigheid`,
`/bopa-beleid`) to `rm-tools/register_assistants.py`, and add a `--dry-run`
flag that lets the registrar run without an admin token (printing payloads
instead of POSTing them).

## Why

The BOPA spec at
`product-docs/superpowers/specs/2026-04-17-bopa-assistant-config.md` was
approved and the workflow is wired up server-side: the `rm-memory` MCP
server is integrated into `rm-assistent`'s `toolIds`, the BOPA skill lives
at `.claude/skills/bopa/SKILL.md`, and `ADMIN_SETUP.md` documents the
9-server registration. **What never shipped** is the user-facing entry
point: the slash prompts. Without them, an advisor opening
`chat.datameesters.nl` has no discoverable way to start a BOPA evaluation
— the workflow is only reachable by typing the right English question and
hoping the LLM picks the right tools. The spec's success criterion (5
assistants + 11 prompts via dry-run) currently fails (5 + 8).

The `--dry-run` flag is in the same spec and serves CI / local sanity
checks without needing a live admin token.

## Success criteria

1. `python3 rm-tools/register_assistants.py --dry-run` exits 0 and reports
   `5 assistants + 11 prompts` (currently 5 + 8).
2. `python3 -m py_compile rm-tools/register_assistants.py` passes.
3. `--dry-run` no longer requires `--token`; running without `--token` and
   without `--dry-run` still errors clearly.
4. The 3 prompt commands `bopa-haalbaarheid`, `bopa-strijdigheid`,
   `bopa-beleid` appear in dry-run output and reference the BOPA flow
   (geocode → list/create session → phase tools).

## Approach

- Append three dicts to the `PROMPTS` list in `register_assistants.py`,
  each with `command`, `name`, `content` matching the existing schema.
  Content templates use `{{adres}}` placeholder (or `{{gemeente}}` where
  appropriate) and instruct the agent to use the rm-memory + databank +
  geoportaal tools per the BOPA skill.
- Add `--dry-run` argparse flag. Make `--token` optional; if not dry-run
  and not supplied, error.
- Implement dry-run: instead of POSTing, print the payload (compact JSON,
  one per line) and count. The summary line still shows
  `Models: N/N` and `Prompts: N/N`, with a `(dry-run)` suffix.
- No changes to ASSISTANTS list — the spec already shipped that part.

## Not doing

- Phase 4–6 slash prompts (`/bopa-omgevingsaspecten`, `/bopa-onderbouwing`,
  `/bopa-toetsing`) — explicit follow-up in the BOPA spec, blocked on
  matching MCP tools.
- Consolidating the 5 specialist assistants — separate concern, separate PR.
- Auto-syncing `.claude/skills/bopa/SKILL.md` with the canonical source —
  also a follow-up.
- End-to-end staging integration test (would require a live OpenWebUI +
  admin JWT). The dry-run smoke is the local validation.
