# ADR-0002: Clerk OIDC SSO via auto-redirect

**Date:** 2026-03-31
**Status:** Accepted

## Context

All \*.datameesters.nl apps share Clerk auth. The chatbot (Python/SvelteKit) can't use `@clerk/react` ClerkProvider like the React apps do.

## Decision

Use OpenWebUI's built-in OIDC support with Clerk as the provider. When the login form is disabled and OIDC is configured, auto-redirect to Clerk. Clerk recognizes the existing session from datameesters.nl and authenticates instantly.

## Alternatives Considered

1. **Shared cookie SSO (read `__session` server-side)** — Rejected. The `__session` cookie is set on `datameesters.nl` only (not `.datameesters.nl`), so it's not visible to subdomains. Clerk's SDK uses the shared `__client_uat` cookie + Frontend API to establish sessions, which requires the JS SDK.

2. **Clerk satellite mode** — Rejected. Requires Clerk Pro plan (paid).

3. **Custom Python middleware reading `__client_uat`** — Rejected. Would need to replicate Clerk SDK logic server-side.

## Consequences

- First visit shows a consent screen (one-time only per user)
- Subsequent visits are instant (Clerk session persists)
- Escape hatch: if OIDC fails, user sees error instead of redirect loop (checked via `?error=` param)
- No dependency on Clerk's paid features
