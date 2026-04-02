# ADR-0001: Fork OpenWebUI

**Date:** 2026-03-31
**Status:** Accepted

## Context

We need a chat interface for the RM AI assistant. Options: configure OpenWebUI via env vars/themes, fork it, or build from scratch.

## Decision

Fork OpenWebUI. Maintain upstream remote for syncing.

## Rationale

- Deep branding (theme, logos, welcome page, Dutch prompts) requires source changes
- Clerk OIDC auto-redirect requires frontend modification
- Custom tool registration scripts need to live alongside the codebase
- OpenWebUI's license allows rebranding for ≤50 users (internal team fits)

## Consequences

- Must sync with upstream monthly to get security fixes and new features
- RM customizations isolated to dedicated files (CSS theme, brand-assets, middleware) to minimize merge conflicts
- Enterprise license needed if team grows beyond 50 users or external clients are added
