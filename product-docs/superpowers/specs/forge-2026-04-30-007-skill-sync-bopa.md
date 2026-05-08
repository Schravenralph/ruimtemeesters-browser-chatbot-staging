# Spec — `scripts/sync-bopa-skill.sh` (BOPA skill drift prevention)

**Date:** 2026-04-30
**Status:** Approved (forge cycle, backlog #2 from 2026-04-30 forge report)
**Repo:** `Ruimtemeesters-Browser-Chatbot`
**Depends on:** `Ruimtemeesters-MCP-Servers/packages/memory/skills/bopa.md` (canonical source)

## 1. Goal

Two copies of the BOPA skill exist and must stay byte-identical:

- **Canonical**: `Ruimtemeesters-MCP-Servers/packages/memory/skills/bopa.md`
  — read by the `@rm-mcp/memory` MCP server at runtime, baked into the
  agent system prompt by the gateway.
- **Mirror**: `Ruimtemeesters-Browser-Chatbot/.claude/skills/bopa/SKILL.md`
  — picked up by Claude Code so contributors hacking on the chatbot
  repo get the same skill content.

Today they drift via manual copy-paste. As of 2026-04-30 the canonical
is 268 lines, the mirror is 84 — a regression that this spec also
unwinds.

This spec ships a sync script + a pre-commit check + the corrective
content sync.

## 2. Non-goals

- Not adding cross-repo CI yet — that needs a PAT secret with read
  access to `Ruimtemeesters-MCP-Servers`. Listed as a follow-up.
- Not making the chatbot mirror authoritative. Edits should always go
  to the canonical first; this script copies one direction only.
- Not symlinking. The two repos can be checked out independently and
  the chatbot must build without the sibling repo present.

## 3. Behavior

### `scripts/sync-bopa-skill.sh`

```
scripts/sync-bopa-skill.sh                      # copy canonical → mirror
scripts/sync-bopa-skill.sh --check              # exit 1 on drift
scripts/sync-bopa-skill.sh --source <path>      # override source path
```

Default source path: `../Ruimtemeesters-MCP-Servers/packages/memory/skills/bopa.md`
(sibling-repo convention used elsewhere in the org).

If the source path doesn't exist:

- **default mode**: error, exit 2 ("source not found, check out
  Ruimtemeesters-MCP-Servers as sibling")
- **`--check` mode**: print a `SKIP` notice on stderr, exit 0 (so
  contributors without the sibling repo aren't blocked)

The mirror file is overwritten verbatim from the source — no header
injection or content transformation. The canonical already opens with
"Deze skill werkt zowel in Claude Code … als in OpenWebUI", so the
provenance is in-band.

`--check` mode does a `cmp -s` between source and mirror. On drift it
prints a one-line summary + the unified diff to stderr.

### `.githooks/sync-bopa-skill-check.sh`

Pre-commit hook fragment that:

1. Runs only when `.claude/skills/bopa/SKILL.md` is staged.
2. Calls `scripts/sync-bopa-skill.sh --check`.
3. Inherits the script's "skip if sibling missing" semantics.

Wired into `.githooks/pre-commit` alongside `no-public-bind-check.sh`.

### Initial content sync (this PR)

Re-copy the canonical 268-line content into the mirror file. Verify
`scripts/sync-bopa-skill.sh --check` exits 0 after the copy.

## 4. Success criteria

| Criterion                                                          | Threshold      | How measured                                                        |
| ------------------------------------------------------------------ | -------------- | ------------------------------------------------------------------- |
| Sync script exists, executable                                     | yes            | `[ -x scripts/sync-bopa-skill.sh ]`                                 |
| Bash syntax check                                                  | pass           | `bash -n scripts/sync-bopa-skill.sh`                                |
| `scripts/sync-bopa-skill.sh --check` against current state exits 0 | yes            | run after content sync                                              |
| Pre-commit hook fragment exists, executable                        | yes            | `[ -x .githooks/sync-bopa-skill-check.sh ]`                         |
| Pre-commit dispatcher invokes it                                   | yes            | grep in `.githooks/pre-commit`                                      |
| Mirror file size after sync                                        | matches source | `cmp -s` source mirror                                              |
| Skip-when-sibling-missing path                                     | exits 0, warns | `BOPA_SKILL_SOURCE=/nonexistent scripts/sync-bopa-skill.sh --check` |

## 5. Validation

1. **Lint:** `bash -n scripts/sync-bopa-skill.sh .githooks/sync-bopa-skill-check.sh`
2. **Sync check (matched):** after copying canonical → mirror,
   `scripts/sync-bopa-skill.sh --check` → exit 0
3. **Sync check (drift):** revert mirror to a prior shorter version,
   `scripts/sync-bopa-skill.sh --check` → exit 1 with diff on stderr
4. **Skip semantics:** `BOPA_SKILL_SOURCE=/tmp/no-such-path scripts/sync-bopa-skill.sh --check`
   → exit 0, "SKIP" on stderr
5. **Pre-commit integration:** stage a drifted SKILL.md, attempt
   commit → blocked with same diff message; sync, re-stage → commit
   succeeds

## 6. Follow-ups

1. Cross-repo CI workflow (`.github/workflows/skill-sync-check.yaml`)
   that checks out `Ruimtemeesters-MCP-Servers` via a PAT secret and
   runs `scripts/sync-bopa-skill.sh --check`. Skipped from this PR
   because the secret needs operator setup.
2. Generalize to `scripts/sync-skills.sh` if a second skill is added
   to `packages/memory/skills/`. For now BOPA is the only skill.
3. Add an `mcp-servers-path` env override pattern to other scripts
   that read from sibling repos, if the pattern recurs.
