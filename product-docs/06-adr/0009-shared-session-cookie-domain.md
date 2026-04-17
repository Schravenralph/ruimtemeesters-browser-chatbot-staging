# ADR-0009: Shared session via .datameesters.nl cookie domain

**Date:** 2026-04-17
**Status:** Proposed

## Context

Multiple surfaces need to share authentication state so users don't re-login when switching between the chat UI and sibling apps:

- `chat.datameesters.nl` — canonical chat UI
- `databank.datameesters.nl`, `geoportaal.datameesters.nl`, etc. — sibling apps with embedded chat panels
- Future `*.datameesters.nl` surfaces

Clerk's `__session` cookie is already scoped to `.datameesters.nl` (established in ADR-0002). OpenWebUI has its own auth cookie that defaults to the specific hostname.

## Decision

Scope OpenWebUI's auth cookie domain to `.datameesters.nl` so that all `*.datameesters.nl` surfaces share the same authenticated session.

For environments where cookie sharing isn't possible (developer tools, non-browser clients), Clerk-minted JWT tokens provide the same identity via Authorization headers.

## Rationale

- Clerk already sets `.datameesters.nl` — extending this to OpenWebUI's cookie is consistent
- Users moving from `chat.datameesters.nl` to a sibling app (or vice versa) stay authenticated
- Deep-links from embedded chat panels to the full chat UI work without re-auth
- JWT fallback covers non-browser clients (Claude Desktop, Cursor, API consumers)

## Consequences

- OpenWebUI's cookie configuration must be customized in the fork (set `domain` on the auth cookie)
- All surfaces under `.datameesters.nl` can read the session cookie — acceptable since they're all RM-controlled
- Cookie scope change must be tested carefully: logout on one surface must invalidate across all surfaces
- Dev/staging environments on different domains (e.g., `localhost`) are unaffected — cookie domain only applies in production
