# ADR-0019: Allow `@clerk/clerk-js` in the chatbot frontend for token-minting only

**Date:** 2026-05-20
**Status:** Accepted
**Amends:** ADR-0002 (Clerk OIDC SSO via auto-redirect)
**Driver:** WI-006 (cross-repo integration with the Ruimtemeesters Document-Generator embed)

## Context

ADR-0002 rejected two specific Clerk integration paths for the chatbot frontend:

1. `@clerk/react`'s `ClerkProvider` — because the chatbot is SvelteKit, not React.
2. Clerk's "satellite mode" — because it requires a paid Pro plan.

That decision was correct for SSO (the chatbot still signs users in via OpenWebUI's built-in OIDC handler, with Clerk acting as the OIDC provider). It also left the chatbot's _frontend_ without any way to hold a Clerk-issued JWT: the OAuth id-token that the OIDC flow produces is stored in the `HttpOnly` `oauth_id_token` cookie, reachable only by the chatbot's backend (see `backend/open_webui/utils/token_forwarding.py`, which forwards it to sibling services like Geoportaal and Databank).

WI-006 brings a new requirement that ADR-0002 didn't anticipate: an embedded Web Component (`<rm-doc-generator>`) that the _frontend_ mounts and that calls its own backend on `doc-gen.datameesters.nl/api/*` with `Authorization: Bearer <clerk-jwt>`. The token has to be present in the chatbot's frontend JS — there is no way to inject it from the backend without weakening the `HttpOnly` invariant.

## Decision

Allow `@clerk/clerk-js` (the framework-agnostic vanilla browser client) in the chatbot frontend, **for the narrow purpose of minting Clerk-issued JWTs against an existing Clerk session**. The package is loaded lazily on routes that need it (today: `/documents`), not on every page.

This is not a reopening of ADR-0002. The specific things ADR-0002 rejected are still rejected:

- We are **not** adding `@clerk/react` or any framework-binding wrapper.
- We are **not** enabling satellite mode.
- We are **not** asking Clerk JS to establish a new session — the user is already signed in via the OIDC flow, with the `.datameesters.nl`-scoped `__client_uat` cookie marking the session. Clerk JS reads that and produces tokens; it does not redirect or take over the auth UI.

## Alternatives considered

| Option                                                                                                                    | Why rejected                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Don't integrate at all.**                                                                                               | Drops WI-006's prod readiness on the floor and forces all DG use through the standalone SPA at `doc-gen.datameesters.nl`, which defeats the whole point of the Web-Component embed pattern (ADR-0008 + ADR-0011).                                                                        |
| **Backend `/api/v1/doc-gen/token` endpoint** that reads the `oauth_id_token` HttpOnly cookie and returns the JWT as JSON. | Weakens the `HttpOnly` invariant the OIDC flow deliberately establishes — once a custom endpoint can read out the cookie, an XSS lapse on a chatbot page leaks the token to attacker JS. Clerk JS keeps the token in JS memory only, never round-tripping it through a chatbot endpoint. |
| **Iframe `doc-gen.datameesters.nl`** instead of mounting the Web Component.                                               | Rejected by Document-Generator's ADR-002 ("iframe + postMessage: heavier, harder to share the user session, awkward layout sizing, more friction for the chatbot's read+write API") and undermines the service-pattern this ADR-0011 endorses.                                           |
| **Service-mode dev POC** (`VITE_API_KEY` only).                                                                           | Useful as an intermediate step, but doesn't ship a production path. Falls short of WI-006's acceptance criteria.                                                                                                                                                                         |

## Consequences

- **+1 npm dependency** in the chatbot frontend: `@clerk/clerk-js` (~30 KB gzipped at v5). Loaded dynamically (`await import()`) so non-/documents routes don't pay the cost.
- **+1 public env var:** `PUBLIC_CLERK_PUBLISHABLE_KEY`. The same value already used by other `.datameesters.nl` front-ends (Geoportaal, Databank); safe to ship in the bundle (it's the publishable key, not the secret one).
- The chatbot's frontend is now responsible for keeping the Clerk JWT fresh on routes that consume it. The `docGenAuth` module subscribes to `clerk.addListener` and re-pushes the token into the embed's `auth-token` attribute on rotation.
- WI-008 (LLM → `proposeEdit` wiring) inherits this auth pipeline for free — the same `docGenAuth.getDocGenAuthToken()` works in any chatbot route that calls into the DG embed.
- Onboarding gains one extra setup step: configure `PUBLIC_CLERK_PUBLISHABLE_KEY` in `.env.rm`. Documented in `.env.rm.example`.

## Followups

- If a third frontend integration ever needs the same Clerk token (e.g., the chatbot rendering a Databank widget that calls Databank's API directly), the `docGenAuth` module's naming becomes too narrow; refactor to a generic `clerkAuth` module then.
- Consider whether to swap to Clerk's full SDK (sign-in/-out flows in JS) if we ever want to drop OpenWebUI's OIDC handler. Outside this ADR's scope; the OIDC flow stays as-is.
