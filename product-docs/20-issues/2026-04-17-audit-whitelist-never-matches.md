# Audit whitelist `AUDIT_INCLUDED_PATHS` never matches

**Filed:** 2026-04-17
**Severity:** High (audit gap — writes to /api/v1/chat, /tools, /models, /auths are not being logged)
**Source:** Cursor Bugbot comment on merged PR #5 (`rm/audit-and-docs`)
**Introduced by:** `docker-compose.rm.yaml` line 87 (earliest seen on branch `rm/audit-and-docs`)

## Symptom

`AUDIT_INCLUDED_PATHS` is set to the full-form paths `/api/v1/chat,/api/v1/tools,/api/v1/models,/api/v1/auths`, but the audit middleware produces the regex

```
^/api(?:/v1)?/(api/v1/chat|api/v1/tools|api/v1/models|api/v1/auths)\b
```

after env.py strips the leading `/` (env.py:875). Matching `/api/v1/chat/completions`:

- `^/api(?:/v1)?/` consumes `/api/v1/`, leaving `chat/completions`
- The alternation requires literal `api/v1/...` next, which is not present
- `pattern.match()` returns `None`

Consequence: `_should_skip_auditing` treats EVERY whitelisted path as "not in whitelist" and skips it. Audit logging on the most important endpoints is effectively off.

## Reproduction

```bash
docker exec rm-chatbot python3 -c "
from open_webui.env import AUDIT_INCLUDED_PATHS
import re
included = AUDIT_INCLUDED_PATHS
pattern = re.compile(r'^/api(?:/v1)?/(' + '|'.join(included) + r')\b')
print('pattern:', pattern.pattern)
print('match /api/v1/chat/completions?', bool(pattern.match('/api/v1/chat/completions')))
print('match /api/v1/auths/signin?', bool(pattern.match('/api/v1/auths/signin')))
"
```

Expected: both True. Actual: both False.

## Fix

`AUDIT_INCLUDED_PATHS` is meant to hold **segment-after-prefix tokens**, not full paths. Change the compose value from

```
AUDIT_INCLUDED_PATHS=/api/v1/chat,/api/v1/tools,/api/v1/models,/api/v1/auths
```

to

```
AUDIT_INCLUDED_PATHS=chat,tools,models,auths
```

This matches the format used by `AUDIT_EXCLUDED_PATHS` in env.py (`/chats,/chat,/folders` → lstripped to `chats,chat,folders`).

## Verification

After fix:

```bash
docker exec rm-chatbot python3 -c "
from open_webui.env import AUDIT_INCLUDED_PATHS
import re
pattern = re.compile(r'^/api(?:/v1)?/(' + '|'.join(AUDIT_INCLUDED_PATHS) + r')\b')
print('match /api/v1/chat/completions?', bool(pattern.match('/api/v1/chat/completions')))
print('match /api/v1/auths/signin?', bool(pattern.match('/api/v1/auths/signin')))
print('match /api/v1/users/list?', bool(pattern.match('/api/v1/users/list')))
"
```

Expected:
- `/api/v1/chat/completions` → True
- `/api/v1/auths/signin` → True
- `/api/v1/users/list` → False (not whitelisted)

Functional check: make an authenticated POST to `/api/v1/chat/completions` and observe a new line in `data/logs/audit.log`.

## Scope note

This env value also exists in `.env.rm.example` comments (if any) and any deployment overrides. Grep before merging.
