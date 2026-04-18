# OAuth `cookie_expires` not passed to `token` / `oauth_id_token` cookies

**Filed:** 2026-04-17
**Status:** **RESOLVED** in commit `26ec859c1` on main (pre-dated this filing)
**Severity:** High (stated — cross-subdomain cookie persistence under `.datameesters.nl` depended on explicit `expires` for certain browsers/proxies)
**Source:** Cursor Bugbot comment on PR #7 (`fix/clerk-oauth-session-cookie`), reviewing commit `5ce172943`

## Summary

Bugbot correctly flagged that `backend/open_webui/utils/oauth.py` computed `cookie_expires` but only applied it to the `oauth_session_id` cookie. The primary `token` cookie (line 1636) and the `oauth_id_token` cookie (line 1647) still only set `max_age`, defeating the stated goal of PR #7 (explicit `expires` timestamp for cross-subdomain reliability).

## Status

The follow-up commit `26ec859c1` ("fix: add expires to token and oauth_id_token cookies too") was merged into main at `2026-04-17 08:51:43 +0200`, four minutes before PR #7 itself merged. Current main already has the intended `{'max_age': cookie_max_age, 'expires': cookie_expires}` kwargs on all three `set_cookie` calls:

- Line 1642: `token` cookie
- Line 1653: `oauth_id_token` cookie
- Line 1691: `oauth_session_id` cookie

Verification:

```bash
grep -nE "set_cookie|max_age.*expires.*cookie_expires" backend/open_webui/utils/oauth.py | head -10
# should show all three set_cookie blocks passing both max_age and expires
```

## Why this issue is filed anyway

Memory entry `feedback_pr_review_bots.md` says to check and fix bugbot comments before/during merge. Here the fix landed _before_ merge but _after_ bugbot's review snapshot, so the open comment on the PR looked unresolved in a session-close audit. Filing this doc makes the resolution traceable and closes the audit loop.

## No PR required

Code already matches bugbot's recommendation. The Cursor "Fix in Cursor" button on the stale comment is now a no-op.
