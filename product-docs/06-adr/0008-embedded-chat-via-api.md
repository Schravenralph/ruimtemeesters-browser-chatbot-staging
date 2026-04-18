# ADR-0008: Embedded chat via REST API, not iframe

**Date:** 2026-04-17
**Status:** Proposed

## Context

Sibling apps (Databank, Geoportaal, Dashboarding, etc.) should show chat history and allow quick AI queries without leaving the app. Two approaches were considered:

| Approach                     | Pros                                                            | Cons                                                                                                            |
| ---------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Iframe the full OpenWebUI UI | Zero frontend code                                              | Must relax X-Frame-Options / CSP; full chat UI crammed into a panel; clunky UX; hard to style to match host app |
| REST API + custom views      | Purpose-built UX per app; lightweight; fetch only what's needed | Must build and maintain the views; depends on API stability                                                     |

## Decision

Use the **OpenWebUI REST API + custom views** approach. Each sibling app:

1. Calls the OpenWebUI REST API with the user's JWT
2. Retrieves chats and messages relevant to the app's context
3. Renders them in a design that fits the host app
4. Provides a "Open in full chat" action that deep-links to `chat.datameesters.nl/c/<chat-id>`

The shared cookie domain (ADR-0009) means the user lands authenticated — no re-login.

## Rationale

- Each app has different layout constraints — a policy doc viewer and a map interface need different chat panel designs
- Iframe embedding forces the host app to relax security headers (X-Frame-Options, CSP frame-ancestors) which is undesirable
- API calls let the host app fetch only what it needs (e.g., last 5 chats, messages for a specific topic) rather than loading the entire chat UI
- Deep-linking to the canonical UI for full conversations keeps the embedded views lightweight

## Consequences

- Need to build a shared TypeScript client library for the OpenWebUI API (one library, all sibling apps import it)
- Each sibling app needs a small chat panel component (scope varies per app)
- OpenWebUI's API becomes a cross-team dependency — pin version, test on upgrade
- No CSP relaxation needed — cleaner security posture
