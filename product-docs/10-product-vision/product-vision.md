# Product Vision — Ruimtemeesters AI

## What it is

A multi-surface AI platform that gives the Ruimtemeesters team conversational access to the entire application ecosystem. Built as a fork of OpenWebUI with deep integrations into each sibling application — accessible from the canonical chat UI, embedded panels in sibling apps, and developer tools like Claude Desktop.

## Who it's for

- **Now:** Internal RM team (consultants, analysts, sales, admins)
- **Later:** External clients (municipalities, government) with scoped access

## Why it exists

Team members switch between multiple applications (Databank, Geoportaal, Dashboarding, TSA, Riens, etc.) to get answers that span domains. The chatbot provides a single entry point where a natural language question fans out across the right apps and returns a unified answer.

## Key Capabilities

1. **Search beleidsdocumenten** — hybrid keyword + semantic search across all Dutch policy documents
2. **Query spatial rules** — look up omgevingsregels at any coordinate
3. **Run demographic forecasts** — ML ensemble (Prophet, SARIMA, Holt-Winters) for any gemeente
4. **Track assignments** — DAS/inhuur pipeline with inbox, deadlines, and stage management
5. **Sales intelligence** — gemeente contract status, sales forecasting
6. **Cross-app context** — combine policy + spatial + demographic data in one query
7. **Knowledge graph** — traverse relationships between policies, topics, and organizations
8. **Embedded chat in apps** — access AI and chat history from within any sibling application
9. **Developer tool access** — MCP-native access to RM data from Claude Desktop, Cursor, Claude Code

## Roadmap

| Phase | Status   | Description                                                                                                |
| ----- | -------- | ---------------------------------------------------------------------------------------------------------- |
| A1-A2 | Done     | Fork, brand, Docker, Clerk SSO                                                                             |
| A3    | Done     | 7 direct app tools                                                                                         |
| A4    | Done     | Aggregator cross-app tool                                                                                  |
| A5    | Done     | 5 assistants + 8 prompt templates                                                                          |
| A6    | Done     | Audit logging + docs                                                                                       |
| C1-C5 | Planned  | MCP extension layer                                                                                        |
| D1    | Proposed | LiteLLM proxy for provider routing + cost management ([ADR-0010](../06-adr/0010-litellm-proxy.md))         |
| D2    | Proposed | Shared session cookie across .datameesters.nl ([ADR-0009](../06-adr/0009-shared-session-cookie-domain.md)) |
| D3    | Proposed | OpenWebUI API client library for sibling apps ([ADR-0008](../06-adr/0008-embedded-chat-via-api.md))        |
| D4    | Proposed | Embedded chat panel in pilot sibling app                                                                   |
| D5    | Proposed | Deep-linking from embedded panels to canonical chat UI                                                     |
| D6    | Proposed | Per-user spend dashboards via LiteLLM                                                                      |

See [Multi-Surface Platform Vision](../01-architecture/multi-surface-platform-vision.md) for full architecture and cost analysis.
