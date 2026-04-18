# Multi-Surface AI Platform — Architecture Vision

**Date:** 2026-04-16
**Status:** Draft
**Origin:** Brainstorming session (Ralph + Claude)

---

## 1. Vision Statement

Evolve the Ruimtemeesters AI platform from a single chat interface (chatbot.datameesters.nl) into a multi-surface platform where the same MCP servers, conversation history, and user sessions are accessible from multiple clients: a web chat UI, embedded chat panels in sibling applications, and developer tools like Claude Desktop and Cursor.

---

## 2. Problem

Today, MCP servers are consumed by a single surface — the OpenWebUI fork at chatbot.datameesters.nl. Team members who work inside a specific application (e.g., Databank, Geoportaal) must context-switch to the chatbot to ask questions. Developers using Claude Desktop or Cursor cannot access RM application data through MCP without manual config. There is no way to see chat history from one surface when working in another.

---

## 3. Target Architecture

### 3.1 Surfaces

| Surface                  | Client                                   | Use Case                                                                    |
| ------------------------ | ---------------------------------------- | --------------------------------------------------------------------------- |
| **Canonical chat UI**    | OpenWebUI (chat.datameesters.nl)         | Full-featured chat: all models, assistants, tools, history, admin           |
| **Embedded chat panels** | Custom lightweight views in sibling apps | Quick contextual queries without leaving the app; read chat history         |
| **Developer tools**      | Claude Desktop, Cursor, Claude Code      | MCP-native access to RM data during development (Phase C5, already planned) |

### 3.2 System Diagram

```
                    ┌───────────────────────────────────────────────────────┐
                    │                  USERS                                │
                    │   Browser (chat UI)  │  App panels  │  Dev tools      │
                    └──────────┬───────────┴──────┬───────┴───────┬─────────┘
                               │                  │               │
                    ┌──────────▼──────────────────▼───────────────┘
                    │         Shared SSO (Clerk)                   │
                    │    Cookie domain: .datameesters.nl           │
                    │    JWT auth across all surfaces              │
                    └──────────┬──────────────────┬───────────────┘
                               │                  │
          ┌────────────────────▼──┐    ┌──────────▼──────────────────┐
          │     OpenWebUI Fork    │    │    Sibling App Frontends    │
          │   (canonical chat)    │    │    (embedded chat views)    │
          │                       │    │                             │
          │  SvelteKit UI         │    │  Call OpenWebUI REST API    │
          │  FastAPI backend      │    │  with user's JWT            │
          │  PostgreSQL           │    │  Render history in-app      │
          │  LLM routing          │    │  Deep-link to full chat UI  │
          └───────────┬───────────┘    └─────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │      LiteLLM Proxy    │   ← Provider routing, per-user budgets,
          │     (recommended)     │     model selection, spend tracking
          └───────────┬───────────┘
                      │
     ┌────────────────┼────────────────────────────────────────┐
     │                │                                         │
     ▼                ▼                                         ▼
  Anthropic        OpenAI                                   Ollama
  (Claude)        (GPT-4o/4.1)                            (local LLM)
```

### 3.3 MCP Server Layer (unchanged from Phase C)

```
  OpenWebUI ──► MCP Client ──┬──► mcp-databank        :3101
  Claude Desktop ──► stdio ──┤──► mcp-geoportaal      :3102
  Cursor ──► stdio ──────────┤──► mcp-tsa             :3103
                             ├──► mcp-dashboarding    :3104
                             ├──► mcp-riens           :3105
                             ├──► mcp-sales-predictor :3106
                             ├──► mcp-opdrachten      :3107
                             └──► mcp-aggregator      :3108
```

The MCP servers are the shared integration layer. Transport differs by surface (HTTP for OpenWebUI, stdio for dev tools), but the tool definitions and business logic are identical.

---

## 4. Key Design Decisions

### 4.1 OpenWebUI as the Backend, Not Just a UI

OpenWebUI is not merely a chat frontend — it is the backend of record for conversations, user sessions, and tool orchestration. The PostgreSQL database it manages is the single source of truth for chat history. Other surfaces consume this data via the OpenWebUI REST API, not by duplicating storage.

### 4.2 Embedded Chat via API, Not Iframe

Two options exist for showing chat in sibling apps:

| Approach                    | Pros                                                            | Cons                                                                               |
| --------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Iframe**                  | Zero frontend code                                              | Requires relaxing X-Frame-Options/CSP; clunky UX; full chat UI forced into a panel |
| **REST API + custom views** | Purpose-built UX per app; lightweight; only fetch what's needed | Must build and maintain the views                                                  |

**Decision: REST API + custom views.** Each sibling app calls the OpenWebUI API with the user's JWT, retrieves chats and messages, and renders them in a design that fits the app. A "Open in full chat" action deep-links to `chat.datameesters.nl/c/<chat-id>`, where the shared cookie means the user lands authenticated in the same conversation.

### 4.3 Session Sharing via Shared Cookie Domain

All surfaces live under `*.datameesters.nl`. Clerk's `__session` cookie is already scoped to `.datameesters.nl` (per ADR-0002). OpenWebUI's auth cookie should be set to the same domain so that:

- `chat.datameesters.nl` — canonical chat UI
- `app.datameesters.nl` — sibling app with embedded chat panel
- Any future `*.datameesters.nl` surface

all share the same authenticated session. No re-login when switching surfaces.

For environments where cookie sharing isn't sufficient (e.g., dev tools), JWT tokens minted by Clerk provide the same identity.

### 4.4 LiteLLM Proxy for Provider Management

Place a LiteLLM proxy between OpenWebUI and LLM providers. This adds:

- **Provider routing:** Route requests to Claude, GPT-4o, or Ollama based on model selection
- **Per-user spend tracking:** Budget visibility without building custom metering
- **Fallback chains:** If one provider is down, route to another
- **Prompt caching pass-through:** Anthropic's prompt caching works through LiteLLM

OpenWebUI already supports LiteLLM as a provider. This is a configuration change, not a code change.

---

## 5. Cost Analysis: API + OpenWebUI vs. Claude Subscription

### 5.1 Pricing Reference (as of 2026-04-16)

| Model             | Input (per 1M tokens) | Output (per 1M tokens) |
| ----------------- | --------------------- | ---------------------- |
| Claude Opus 4.6   | $15                   | $75                    |
| Claude Sonnet 4.6 | $3                    | $15                    |
| Claude Haiku 4.5  | $1                    | $5                     |

| Subscription | Price       | Notes                                      |
| ------------ | ----------- | ------------------------------------------ |
| Claude Pro   | $20/mo      | Includes web search, artifacts, file tools |
| Claude Max   | $100–200/mo | Higher limits, same features               |

### 5.2 Usage Profiles

| Profile                                                   | Estimated API Cost (Sonnet 4.6) | vs. Subscription                                   |
| --------------------------------------------------------- | ------------------------------- | -------------------------------------------------- |
| **Light chat** (20 msg/day, ~2k in + 1k out each)         | ~$19/mo                         | Roughly equal to Pro                               |
| **Light chat on Haiku**                                   | ~$6/mo                          | Cheaper than Pro                                   |
| **Heavy conversational** (long contexts, docs, artifacts) | $40–100+/mo                     | Pro/Max wins — subscriptions subsidize heavy users |
| **Agentic / coding** (tool loops, long sessions)          | $500–2000/mo                    | Max ($200) dramatically cheaper                    |

### 5.3 When API + OpenWebUI Wins

- Multiple users sharing one budget (pay for tokens, not seats)
- Mixing models by task (Haiku for simple queries, Sonnet for analysis, Opus for complex reasoning)
- Batch processing with prompt caching (cached input ~90% cheaper)
- Need for branding, custom tools, and data sovereignty

### 5.4 When a Subscription Wins

- Heavy or agentic individual use (long sessions, coding loops)
- Bundled features (web search, artifacts rendering, file tools) that would need to be rebuilt or paid for separately via API
- Single-user scenarios where convenience outweighs customization

### 5.5 Recommendation for RM

Use API + OpenWebUI as the primary platform (multi-user, branded, tool-integrated, cost-transparent via LiteLLM). Individual developers who need Claude Desktop for agentic coding should use a separate subscription — that cost is predictable and the usage pattern (long coding sessions) would be expensive on the API.

---

## 6. OpenWebUI API Stability

OpenWebUI's REST API is functional but **not versioned** like a mature product API. Mitigations:

- **Pin the OpenWebUI version** in Docker Compose — no auto-updates
- **Test upgrades** on a staging instance before production
- **Wrap API calls** in a thin client library in sibling apps, so endpoint changes are isolated to one place
- **Monitor the OpenWebUI changelog** on the monthly upstream-sync cadence (already established in fork maintenance policy)

---

## 7. Implementation Phases

This vision builds on the existing Phase A → Phase C roadmap. New work items:

### Phase D — Multi-Surface Platform

| Step | Description                                                             | Depends On      |
| ---- | ----------------------------------------------------------------------- | --------------- |
| D1   | Deploy LiteLLM proxy, configure OpenWebUI to route through it           | Phase A (done)  |
| D2   | Scope OpenWebUI auth cookie to `.datameesters.nl`                       | Phase A2 (done) |
| D3   | Build a thin OpenWebUI API client library (TypeScript) for sibling apps | D2              |
| D4   | Embed chat history panel in one pilot sibling app                       | D3              |
| D5   | Add deep-linking from embedded panel to canonical chat UI               | D4              |
| D6   | Per-user spend dashboards via LiteLLM                                   | D1              |

### Relationship to Existing Phases

```
Phase A (done) ─────► Phase C (MCP layer) ─────► Phase D (multi-surface)
  Fork, brand,           MCP servers,              LiteLLM, embedded
  auth, tools,           OpenWebUI MCP client,     views, session
  assistants             dev tool access            sharing, budgets
```

Phase C and Phase D are independent — they can be worked in parallel. Phase C adds MCP as the integration protocol. Phase D adds surfaces and cost management.

---

## 8. Open Questions

| #   | Question                                                                                                | Impact              |
| --- | ------------------------------------------------------------------------------------------------------- | ------------------- |
| 1   | Which sibling app should pilot the embedded chat panel?                                                 | D4 scope            |
| 2   | Should LiteLLM run as a sidecar in the OpenWebUI compose stack or as a separate service?                | D1 deployment       |
| 3   | Is the OpenWebUI API surface sufficient for the embedded views, or do we need to extend it in the fork? | D3 scope            |
| 4   | Should dev-tool MCP access (Phase C5) go through LiteLLM or directly to providers?                      | D1 + C5 interaction |
| 5   | What per-user spend limits should be set, and should they differ by role?                               | D6 policy           |
