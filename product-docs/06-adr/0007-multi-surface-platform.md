# ADR-0007: Multi-surface platform — OpenWebUI as backend-of-record

**Date:** 2026-04-17
**Status:** Proposed

## Context

The chatbot currently has one surface: the OpenWebUI fork at chatbot.datameesters.nl. Team members working inside sibling apps (Databank, Geoportaal, etc.) must context-switch to the chatbot to ask AI questions. Developers using Claude Desktop or Cursor cannot access RM application data through MCP without manual configuration. Chat history is locked inside the chat UI.

The platform needs to support multiple surfaces — web chat, embedded panels in sibling apps, and developer tools — without duplicating conversation storage or user management.

## Decision

OpenWebUI is the **backend-of-record**, not merely a chat frontend. Its PostgreSQL database is the single source of truth for conversations, user sessions, and tool orchestration. Other surfaces consume this data via the OpenWebUI REST API.

Three surface types:

| Surface              | Client                              | Role                                                     |
| -------------------- | ----------------------------------- | -------------------------------------------------------- |
| Canonical chat UI    | OpenWebUI (chat.datameesters.nl)    | Full-featured: models, assistants, tools, history, admin |
| Embedded chat panels | Custom views in sibling apps        | Contextual queries, read history, deep-link to full UI   |
| Developer tools      | Claude Desktop, Cursor, Claude Code | MCP-native access to RM data (Phase C5)                  |

## Rationale

- One database, one auth system, one place to query history — regardless of which surface the user is on
- OpenWebUI already has the REST API, user management, and tool infrastructure
- Sibling apps don't need their own chat backends — they read from and write to the existing one
- Developer tools connect directly to MCP servers (Phase C5), bypassing OpenWebUI entirely — that's fine because those sessions are developer-local, not shared team conversations

## Consequences

- OpenWebUI's REST API becomes a public interface (internal network), not just an implementation detail — requires stability monitoring
- Sibling apps take a dependency on OpenWebUI's API surface
- Need to pin OpenWebUI version and test upgrades (API is not versioned)
- A thin TypeScript client library should wrap API calls so endpoint changes are isolated
