# Ruimtemeesters Browser Chatbot — Design Spec

**Date:** 2026-03-31
**Status:** Draft
**Author:** Ralph + Claude (brainstorming)

---

## 1. Product Vision

The Ruimtemeesters Browser Chatbot is an AI-powered assistant that gives the RM team (and later, external clients) conversational access to the entire Ruimtemeesters application ecosystem. It is built as a branded fork of OpenWebUI with deep integrations into each sibling application.

### What it is

- A branded, self-hosted chat interface running as a fork of OpenWebUI
- A multi-model AI assistant (OpenAI, Claude, Ollama) with role-based access
- A tool-using agent that can read from and write to all Ruimtemeesters applications
- The glue layer that ties the RM ecosystem into a single conversational interface

### Who it's for

- **Now:** Internal Ruimtemeesters team (consultants, analysts, sales, admins)
- **Later:** External clients (municipalities, government bodies) with scoped, read-only access

### Why it exists

Team members currently switch between multiple applications (Databank, Geoportaal, Dashboarding, TSA, Riens, etc.) to get answers that span domains. The chatbot provides a single entry point where a natural language question can fan out across the right apps and return a unified answer.

---

## 2. Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USERS (Browser)                              │
│                   RM Team → External Clients (later)                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Clerk     │  ← Identity provider (who you are)
                    │   (SSO)     │
                    └──────┬──────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                                                                     │
│              OPENWEBUI FORK  (Ruimtemeesters Branded)               │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │  Chat UI    │  │  Internal    │  │  LLM Providers            │  │
│  │  (branded)  │  │  Roles &     │  │  ┌───────┐ ┌───────────┐ │  │
│  │             │  │  Permissions │  │  │OpenAI │ │  Claude    │ │  │
│  │  Custom     │  │  (what you   │  │  └───────┘ └───────────┘ │  │
│  │  themes     │  │   can do)    │  │  ┌───────┐ ┌───────────┐ │  │
│  │  Skills     │  │              │  │  │Ollama │ │  Others    │ │  │
│  │  Prompts    │  │  Clerk→Role  │  │  │(local)│ │           │ │  │
│  └─────────────┘  │  mapping     │  │  └───────┘ └───────────┘ │  │
│                    └──────────────┘  └───────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              TOOL / FUNCTION LAYER                           │   │
│  │                                                              │   │
│  │  Phase A: OpenWebUI Functions call app REST APIs directly    │   │
│  │  Phase C: + MCP Client connects to per-app MCP Servers      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
         ┌─────────┬───────┼───────┬──────────┬─────────┐
         ▼         ▼       ▼       ▼          ▼         ▼
    ┌─────────┐┌───────┐┌─────┐┌───────┐┌─────────┐┌───────┐
    │Databank ││Geo-   ││Dash-││TSA    ││Workspace││Sales  │
    │         ││portaal││board││Engine ││         ││Predict│
    └─────────┘└───────┘└─────┘└───────┘└─────────┘└───────┘

    + Riens Sales Viewer, Opdrachten Scanner
```

### Integration Model

**Default path:** The chatbot calls app endpoints directly. Each app has its own set of OpenWebUI Functions (Phase A) or MCP server (Phase C).

**Aggregator path:** Only used when a query genuinely spans multiple apps or benefits from fan-out/caching. The Aggregator earns its place through composition, not proxying. No endpoint duplication — if an app has an endpoint, we don't recreate it in the Aggregator.

**Aggregator boundaries:**

| Aggregator does                                                | Aggregator does NOT                        |
| -------------------------------------------------------------- | ------------------------------------------ |
| Cross-app composition (Databank + Geoportaal queries)          | 1:1 proxy of single-app endpoints          |
| Protocol normalization (FastAPI Python apps ↔ Express TS apps) | Business logic (that stays in apps)        |
| Auth token validation & RBAC check                             | Data transformation for specific consumers |
| Rate limiting for the chatbot consumer                         | Being the only way to reach an app         |
| Response trimming for LLM context windows                      | Duplicating existing app endpoints         |

---

## 3. Auth & Permissions

### Three-Layer Auth

```
User opens chatbot
       │
       ▼
┌──────────────┐     Layer 1: IDENTITY
│   Clerk      │     • Who are you?
│   Login/SSO  │     • Clerk JWT issued with user metadata
└──────┬───────┘     • Org, role claims embedded in token
       │
       ▼
┌──────────────┐     Layer 2: CHATBOT PERMISSIONS
│  OpenWebUI   │     • Clerk JWT → OpenWebUI session
│  Auth        │     • Clerk role → OpenWebUI role mapping
│  Middleware   │     • Determines: models, tools, skills, upload limits, admin access
└──────┬───────┘
       │
       ▼  (user sends a message that triggers a tool)
┌──────────────┐     Layer 3: DATA-LEVEL RBAC
│  Tool calls  │     • Clerk JWT forwarded to app
│  App endpoint│     • App validates token + checks permissions
└──────────────┘     • Gemeente-level, dataset-level access
                     • Audit log of who accessed what
```

### Role Model

| Role                         | LLM Models     | Tools Available                                             | Data Access                                | Admin                                |
| ---------------------------- | -------------- | ----------------------------------------------------------- | ------------------------------------------ | ------------------------------------ |
| **Admin**                    | All            | All READ + WRITE                                            | All gemeenten, all datasets                | Manage users, models, tools, prompts |
| **Consultant**               | All            | All READ, selective WRITE (beleidsscan, forecasts, exports) | Assigned gemeenten + public data           | —                                    |
| **Analyst**                  | All            | All READ, WRITE for TSA/forecasts only                      | All datasets (read), own forecasts (write) | —                                    |
| **Sales**                    | OpenAI, Ollama | Riens, Sales Predictor, Opdrachten Scanner                  | Sales data, gemeente status, assignments   | —                                    |
| **External Client** (future) | Ollama only    | READ only, scoped tools                                     | Own gemeente only                          | —                                    |

### Key Auth Decisions

- **Clerk → OpenWebUI mapping:** Custom middleware intercepts Clerk JWT on login, extracts org/role claims, creates/updates OpenWebUI user with the right internal role. Clerk is source of truth — no manual user management in OpenWebUI.
- **Token forwarding:** OpenWebUI Functions forward the user's Clerk JWT to app endpoints. Each app independently validates the token and checks its own permissions. The chatbot never elevates privileges.
- **Tool visibility:** OpenWebUI controls which tools appear per role (UI-level filtering backed by server-side enforcement). A Sales user never sees Databank tools.
- **Audit trail:** Every tool invocation logged (who, what, when, params, response) to the chatbot's PostgreSQL database. Essential for compliance when external clients are added.

---

## 4. OpenWebUI Fork & Branding

### Fork Strategy

OpenWebUI is a SvelteKit app (Python backend + Svelte frontend). We fork the repo, maintain it as a downstream fork with an `upstream` remote for pulling updates.

**What we change:**

- Theme/CSS — full Ruimtemeesters palette
- Logos, favicon, app name, meta tags
- Landing page / onboarding flow
- Default system prompts & skills
- Clerk auth integration (SSO middleware)
- Custom OpenWebUI Functions for app integrations
- Role-to-permission mapping config
- Welcome messages & help content

**What we don't touch:**

- Core chat engine & streaming logic
- Model provider integrations (Ollama, OpenAI, etc.)
- RAG pipeline internals
- WebSocket / real-time infrastructure
- Database schema (extend, don't modify)
- Plugin/Function runtime
- File upload & document handling

### Brand Identity

| Color        | Hex     | Usage                                             |
| ------------ | ------- | ------------------------------------------------- |
| Raisin Black | #161620 | Sidebar, dark UI surfaces                         |
| Klein Blue   | #002EA3 | Primary actions, accents, user message bubbles    |
| Smart White  | #F7F4EF | Backgrounds, text on dark surfaces                |
| Violet       | #7F00FF | User avatars, highlights, secondary accents       |
| Pumpkin      | #F37021 | Warnings, secondary CTAs, write-action indicators |
| Lion         | #9C885C | Tertiary accents                                  |
| Mystified    | #C3D7C1 | Success states, read-action indicators            |

Additional service-specific colors from Riens Sales Viewer: servicedesk (#00BFFF), advies (#FFD700), detachering (#FF5722), bemiddeling (#4CAF50).

### Fork Maintenance

- **Git setup:** `origin` → your fork, `upstream` → open-webui/open-webui
- **Update cadence:** Pull upstream monthly (or on major releases). Merge into `upstream-sync` branch first, resolve conflicts, test, then merge to `main`.
- **Conflict minimization:** All RM customizations in clearly separated files. Theme overrides in a dedicated CSS file, not scattered edits. Custom components in their own directory. Clerk middleware as a separate module.

---

## 5. Tools & Integration Layer

### Per-App Tool Inventory

#### Databank (Policy docs, knowledge graph, semantic search)

| Tool                  | Description                                                      | Type  |
| --------------------- | ---------------------------------------------------------------- | ----- |
| search_beleid         | Hybrid search (keyword + semantic) across policy documents       | READ  |
| query_knowledge_graph | Traverse Neo4j relationships between policies, topics, gemeenten | READ  |
| start_beleidsscan     | Trigger a new scan/crawl for a municipality's policy documents   | WRITE |
| review_document       | Check/update review workflow state for scanned documents         | WRITE |

#### Geoportaal (3D maps, spatial rules, alerts)

| Tool                | Description                                             | Type  |
| ------------------- | ------------------------------------------------------- | ----- |
| query_spatial_rules | Look up regels (rules) for a location or policy area    | READ  |
| get_air_quality     | Retrieve luchtkwaliteit data for a gemeente or location | READ  |
| get_weather         | Weather info for a location                             | READ  |
| export_map          | Generate PDF/DOCX export of a spatial view              | WRITE |
| create_alert        | Set up monitoring presets for locations                 | WRITE |

#### Dashboarding (Primos demographics, CBS data)

| Tool             | Description                                                | Type  |
| ---------------- | ---------------------------------------------------------- | ----- |
| query_primos     | Population/housing projections by gemeente, year, category | READ  |
| get_cbs_stats    | Central Bureau of Statistics demographic data              | READ  |
| trigger_cbs_sync | Start a fresh CBS data synchronization                     | WRITE |

#### TSA Engine (Demographic forecasting, ML ensemble)

| Tool                 | Description                                                      | Type  |
| -------------------- | ---------------------------------------------------------------- | ----- |
| run_forecast         | Execute demographic projection (Prophet, SARIMA, ensemble, etc.) | WRITE |
| run_backtest         | Validate forecast accuracy against historical data               | WRITE |
| get_forecast_results | Retrieve completed forecast data with confidence intervals       | READ  |

#### Riens Sales Viewer (Municipal geo viz, sales intelligence)

| Tool                     | Description                                                  | Type |
| ------------------------ | ------------------------------------------------------------ | ---- |
| get_gemeente_status      | Active/archived municipalities, contract status per province | READ |
| sales_intelligence_query | Insights from the sales intelligence map                     | READ |

#### Sales Predictor (HorecA forecasting)

| Tool                       | Description                                                 | Type  |
| -------------------------- | ----------------------------------------------------------- | ----- |
| run_sales_forecast         | Execute HorecA sales prediction (Prophet, SARIMA, ensemble) | WRITE |
| get_sales_forecast_results | Retrieve predictions with model comparison metrics          | READ  |

#### Opdrachten Scanner (DAS/inhuur scanning)

| Tool               | Description                                              | Type  |
| ------------------ | -------------------------------------------------------- | ----- |
| search_assignments | Find matching DAS/inhuur assignments from TenderNED etc. | READ  |
| trigger_scan       | Run a fresh scan against assignment platforms            | WRITE |

#### Workspace (Team hub, notifications)

| Tool              | Description                               | Type |
| ----------------- | ----------------------------------------- | ---- |
| get_notifications | Retrieve team notifications and updates   | READ |
| get_team_info     | Team member details via Clerk integration | READ |

### Cross-App Queries (via Aggregator)

These are cases where the Aggregator adds genuine value — combining data from multiple apps:

- **Beleid + spatial rules:** "Zoek beleid over luchtkwaliteit en toon gerelateerde regels op de kaart" → Databank + Geoportaal
- **Demographics + policy context:** "Geef de bevolkingsprognose voor Utrecht met relevante beleidsstukken" → Dashboarding + Databank
- **Contract status + policy coverage:** "Welke gemeenten met actieve contracten hebben beleid over woningbouw?" → Riens + Databank
- **Forecast vs actuals:** "Vergelijk de demografische forecast met de CBS werkelijkheid" → TSA + Dashboarding

---

## 6. Skills, Prompts & Custom Assistants

### Pre-Built Assistants (Modelfiles)

Each assistant is a Modelfile: system prompt + model config + curated tool list. Users pick one to start a conversation, or use the generalist. All respect role-based tool visibility.

#### Beleidsadviseur

- **Domain:** Policy documents, knowledge graph, spatial rules
- **Apps:** Databank, Geoportaal
- **Tools:** search_beleid, query_knowledge_graph, query_spatial_rules, export_map
- **Persona:** Expert in Dutch policy documents. Understands Omgevingswet context. Can search beleidsstukken, explain policy implications, compare gemeente policies, and show relevant rules on the map.

#### Demografie Analist

- **Domain:** Population data, demographic forecasting
- **Apps:** Dashboarding, TSA
- **Tools:** query_primos, get_cbs_stats, run_forecast, run_backtest, get_forecast_results
- **Persona:** Specialist in demographic data. Queries Primos/CBS data, runs forecasts with different models, explains trends, compares projections across gemeenten and time horizons.

#### Ruimtelijk Adviseur

- **Domain:** Spatial planning, 3D data, environmental monitoring
- **Apps:** Geoportaal, Databank
- **Tools:** query_spatial_rules, get_air_quality, get_weather, export_map, create_alert, search_beleid
- **Persona:** Spatial planning expert. Queries 3D building data, air quality, weather, and spatial rules. Generates map exports and sets up monitoring alerts. Links spatial data to relevant policy context.

#### Sales Adviseur

- **Domain:** Sales intelligence, assignments, forecasting
- **Apps:** Riens Sales Viewer, Sales Predictor, Opdrachten Scanner
- **Tools:** get_gemeente_status, sales_intelligence_query, search_assignments, trigger_scan, run_sales_forecast
- **Persona:** Business development assistant. Shows gemeente contract status, finds matching TenderNED assignments, runs sales forecasts, provides market intelligence. Knows the Servicedesk Leefomgeving context.

#### Ruimtemeesters Assistent

- **Domain:** All
- **Apps:** All
- **Tools:** All (filtered by user role)
- **Persona:** General-purpose Ruimtemeesters assistant. Routes to the right app based on the question. The default assistant when no specialist is needed.

### Prompt Templates

| Command            | Description                                         |
| ------------------ | --------------------------------------------------- |
| `/beleidsscan`     | Start a policy scan for a gemeente                  |
| `/prognose`        | Run demographic forecast for a gemeente             |
| `/vergelijk`       | Compare two gemeenten on policy/demographics        |
| `/opdrachten`      | Search TenderNED for matching assignments           |
| `/rapport`         | Generate an export/report from current conversation |
| `/luchtkwaliteit`  | Get air quality data for a location                 |
| `/gemeente-status` | Check contract status for a gemeente                |
| `/help`            | Show available commands and capabilities            |

---

## 7. Deployment & Infrastructure

### Docker Compose Stack

```yaml
# Conceptual structure — not a literal docker-compose file
services:
  openwebui: # Forked OpenWebUI (SvelteKit + Python backend)
  ollama: # Local LLM inference (GPU passthrough)
  chatbot-db: # PostgreSQL (conversations, roles, audit log)
```

Connected to existing app stacks via shared Docker network (`rm-network`).

### Key Infrastructure Decisions

- **Self-contained stack:** Own docker-compose with OpenWebUI, Ollama, PostgreSQL. Connects to existing app stacks over shared network. Each app remains independently deployable.
- **PostgreSQL (not SQLite):** Multi-user with audit logging requires a real database. Consistent with the rest of the RM ecosystem. Chat logs as queryable tables enables analytics.
- **Ollama with GPU:** GPU passthrough for local model inference. Persistent volume for model files. Initial models: llama3.1, mistral, codestral.
- **Network topology:** Shared Docker network for service-to-service communication by container name. Only the chatbot's port faces outward (configurable, e.g. 3333). Internal app ports not publicly exposed.
- **Port:** Configurable — not hardcoded. Default TBD based on what's available in the environment.

### Environment Configuration

```env
# LLM Providers
OLLAMA_BASE_URL=http://ollama:11434
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Auth
CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...

# App Endpoints (direct)
DATABANK_API_URL=http://databank-api:3001
GEOPORTAAL_API_URL=http://geoportaal-api:3002
DASHBOARDING_API_URL=http://dashboarding-api:3003
TSA_API_URL=http://tsa-api:8000
RIENS_API_URL=http://riens-api:3004
SALES_PREDICTOR_API_URL=http://sales-predictor-api:8001
OPDRACHTEN_API_URL=http://opdrachten-api:3005
WORKSPACE_API_URL=http://workspace-api:3006

# Aggregator (cross-app queries)
AGGREGATOR_API_URL=http://aggregator-api:3010

# Branding
APP_NAME=Ruimtemeesters AI
APP_FAVICON_URL=/brand-assets/favicon.ico
APP_LOGO_URL=/brand-assets/logo.svg
```

### Fork Maintenance Workflow

- **Git remotes:** `origin` → your-org/ruimtemeesters-browser-chatbot, `upstream` → open-webui/open-webui
- **Update cadence:** Monthly (or on major releases)
- **Process:** Pull upstream → merge into `upstream-sync` branch → resolve conflicts → test → merge to `main`
- **Conflict minimization:** RM customizations in clearly separated files/directories. Theme overrides in dedicated CSS, not scattered edits. Custom components in own directory. Clerk middleware as separate module.

---

## 8. Docs Folder Structure

```
docs/
├── 00-onboarding/
│   ├── getting-started.md            # Dev setup, fork management, running locally
│   ├── openwebui-fork-guide.md       # How to pull upstream changes, resolve conflicts
│   └── architecture-overview.md      # High-level system diagram + component map
│
├── 01-architecture/
│   ├── system-design.md              # Full architecture (from this spec)
│   ├── auth-flow.md                  # Clerk → OpenWebUI → App RBAC chain
│   ├── integration-model.md          # Direct app calls vs Aggregator decision framework
│   └── llm-provider-strategy.md      # Multi-provider setup, model selection per role
│
├── 04-policies/
│   ├── fork-maintenance.md           # Rules for keeping fork mergeable with upstream
│   ├── tool-development.md           # How to build new OpenWebUI Functions/Tools
│   ├── branding-guide.md             # Color palette, logo usage, tone of voice
│   └── security-and-permissions.md   # RBAC rules, token handling, audit requirements
│
├── 06-adr/
│   ├── 0001-fork-openwebui.md        # Why fork vs configure
│   ├── 0002-clerk-plus-openwebui-auth.md  # Auth layering decision
│   ├── 0003-aggregator-boundaries.md # When to use Aggregator vs direct
│   └── 0004-mcp-extension-layer.md   # Phase C: MCP architecture decision
│
├── 10-product-vision/
│   ├── product-vision.md             # What this product is, who it's for, why it exists
│   ├── user-personas.md              # Internal roles, future external clients
│   └── roadmap.md                    # Phase A → Phase C → external clients
│
├── 20-issues/                        # Issue files as they arise
│
├── 25-assistants/
│   ├── beleidsadviseur.md            # System prompt, tools, behavior spec
│   ├── demografie-analist.md         # System prompt, tools, behavior spec
│   ├── ruimtelijk-adviseur.md        # System prompt, tools, behavior spec
│   ├── sales-adviseur.md             # System prompt, tools, behavior spec
│   └── ruimtemeesters-assistent.md   # Generalist system prompt, tools, behavior spec
│
├── 30-tools/
│   ├── databank-tools.md             # Tool specs: endpoints, params, responses
│   ├── geoportaal-tools.md
│   ├── dashboarding-tools.md
│   ├── tsa-tools.md
│   ├── riens-tools.md
│   ├── sales-predictor-tools.md
│   ├── opdrachten-tools.md
│   ├── workspace-tools.md
│   └── aggregator-tools.md           # Cross-app composition tools
│
├── 70-sprint-backlog/                # Sprint files as work begins
│
├── 80-feature-backlog/               # Feature requests and planned work
│
└── superpowers/
    ├── specs/                        # Design specs (including this document)
    └── plans/                        # Implementation plans
```

### Unique folders

- **25-assistants/:** Documents system prompts, tool configs, and expected behaviors for each pre-built assistant. Source of truth for Modelfile generation.
- **30-tools/:** Per-app integration specs. Each file defines endpoints called, parameters, response shapes, error handling, and permission requirements.
- **06-adr/:** Architecture Decision Records capturing key decisions with context and rationale.
- **10-product-vision/:** Product vision, personas, and roadmap. This repo is the ecosystem glue.

---

## 9. Phase Breakdown

### Phase A — Foundation + Direct App Integration

#### A1. Fork & Brand

- Fork OpenWebUI, set up upstream remote
- Apply Ruimtemeesters branding (theme CSS, logos, favicon, app name)
- Custom landing page with RM identity
- Configure multi-provider LLM (Ollama, OpenAI, Claude)
- Docker Compose with OpenWebUI + Ollama + PostgreSQL
- **Deliverable:** Branded chatbot running locally, multi-model, no app integrations yet

#### A2. Auth Integration

- Clerk SSO middleware in the OpenWebUI fork
- Clerk JWT → OpenWebUI role mapping
- Role-based model and tool visibility
- Token forwarding mechanism for app calls
- **Deliverable:** Users log in via Clerk, see tools/models matching their role

#### A3. Tool Layer — Direct App Integration

- OpenWebUI Functions for each app (Python, calling app REST endpoints directly)
- Databank tools: search_beleid, query_knowledge_graph, start_beleidsscan, review_document
- Geoportaal tools: query_spatial_rules, get_air_quality, get_weather, export_map, create_alert
- Dashboarding tools: query_primos, get_cbs_stats, trigger_cbs_sync
- TSA tools: run_forecast, run_backtest, get_forecast_results
- Riens tools: get_gemeente_status, sales_intelligence_query
- Sales Predictor tools: run_sales_forecast, get_sales_forecast_results
- Opdrachten tools: search_assignments, trigger_scan
- Workspace tools: get_notifications, get_team_info
- **Deliverable:** Chatbot can read from and write to all apps via direct endpoints

#### A4. Aggregator — Cross-App Composition

- Extend Aggregator with cross-app endpoints (only where composition adds value)
- Beleid + spatial rules (Databank + Geoportaal)
- Demographics + policy context (Dashboarding + Databank)
- Contract status + policy coverage (Riens + Databank)
- Forecast vs actuals (TSA + Dashboarding)
- OpenWebUI Functions that call Aggregator for these composite queries
- **Deliverable:** Cross-app queries work through Aggregator, no endpoint duplication

#### A5. Assistants & Prompts

- Create Modelfiles for 5 pre-built assistants (Beleidsadviseur, Demografie Analist, Ruimtelijk Adviseur, Sales Adviseur, Ruimtemeesters Assistent)
- System prompts with RM domain knowledge and tone
- Prompt templates for /beleidsscan, /prognose, /vergelijk, /opdrachten, /rapport, /luchtkwaliteit, /gemeente-status, /help
- Welcome messages and onboarding flow
- **Deliverable:** Full chatbot product with specialized assistants and prompt library

#### A6. Audit & Docs

- Tool invocation audit logging to PostgreSQL
- Product docs folder (full structure from section 8)
- ADRs for key decisions
- Onboarding guide for developers
- **Deliverable:** Production-ready Phase A with full documentation

### Phase C — MCP Extension Layer

#### C1. MCP Server Infrastructure

- MCP server scaffold (TypeScript, matching RM ecosystem)
- Shared auth middleware (Clerk JWT validation)
- Tool schema generation from Zod validators (reuse Aggregator's Zod schemas)
- MCP server Docker container template
- **Deliverable:** Reusable MCP server template with auth and schema generation

#### C2. Per-App MCP Servers

- One MCP server per app, wrapping app endpoints as MCP tools
- Each server lives in its own directory (or alongside its app repo)
- Tool descriptions optimized for LLM consumption (clear, concise, with examples)
- Same tools as Phase A Functions, but now via MCP protocol
- **Deliverable:** All app tools accessible via MCP

#### C3. Aggregator MCP Server

- Wraps Aggregator cross-app endpoints as MCP tools
- Automatic Zod → MCP tool schema conversion
- Maintains the same composition logic from Phase A
- **Deliverable:** Cross-app queries also available via MCP

#### C4. OpenWebUI MCP Client Integration

- Connect OpenWebUI fork to MCP servers (may require fork customization)
- MCP tool discovery → automatic tool registration in OpenWebUI
- Migrate Phase A Python Functions to MCP client calls
- Role-based MCP server access (which servers each role can reach)
- **Deliverable:** OpenWebUI uses MCP instead of direct HTTP calls

#### C5. External Tool Consumers

- Same MCP servers usable from Claude Code, Cursor, other AI tools
- Developer-facing MCP config for local development
- Documentation for connecting external tools to RM MCP servers
- **Deliverable:** MCP servers are a shared AI interface, not chatbot-specific

### Phase Dependencies

```
A1 Fork → A2 Auth → A3 Tools → A4 Aggregator → A5 Assistants → A6 Audit+Docs

then

C1 Infra → C2 App MCPs → C3 Aggregator MCP → C4 Client → C5 External
```

Note: A5 (Assistants) and A6 (Audit+Docs) can run in parallel with A3/A4.

---

## 10. Tech Stack Summary

| Component                 | Technology                                                      |
| ------------------------- | --------------------------------------------------------------- |
| Chat UI                   | SvelteKit (OpenWebUI fork)                                      |
| Backend                   | Python (OpenWebUI backend)                                      |
| Database                  | PostgreSQL                                                      |
| Local LLM                 | Ollama (llama3.1, mistral, codestral)                           |
| Remote LLMs               | OpenAI (GPT-4o/GPT-4.1), Anthropic (Claude)                     |
| Auth (identity)           | Clerk                                                           |
| Auth (chatbot)            | OpenWebUI internal roles                                        |
| App integration (Phase A) | OpenWebUI Functions (Python) → REST APIs                        |
| App integration (Phase C) | MCP servers (TypeScript)                                        |
| Aggregator                | Existing Ruimtemeesters-Aggregator (Express + TypeScript + Zod) |
| Container orchestration   | Docker Compose                                                  |
| Network                   | Shared Docker network (rm-network)                              |

---

## 11. Sibling Application Reference

| App                               | Stack                                                    | Purpose                                                | Chatbot Integration                                                         |
| --------------------------------- | -------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------- |
| Ruimtemeesters-Databank           | Express + TS, MongoDB, PostgreSQL+PostGIS, Neo4j, Redis  | Policy doc discovery, knowledge graph, semantic search | search_beleid, query_knowledge_graph, start_beleidsscan, review_document    |
| Ruimtemeesters-Geoportaal         | Express 5 + TS, PostgreSQL, OpenLayers, Cesium 3D        | Geospatial policy mapping, 3D buildings, air quality   | query_spatial_rules, get_air_quality, get_weather, export_map, create_alert |
| Ruimtemeesters-Dashboarding       | Express 5 + TS, React 19, PostgreSQL                     | Primos demographics, CBS data sync                     | query_primos, get_cbs_stats, trigger_cbs_sync                               |
| Ruimtemeesters-TSA                | FastAPI + Python, PostgreSQL, Prophet/SARIMA/ML ensemble | Demographic time series forecasting                    | run_forecast, run_backtest, get_forecast_results                            |
| Riens-Sales-Viewer                | Express + TS, React 19, PostgreSQL+PostGIS, OpenAI       | Municipal geo viz, sales intelligence                  | get_gemeente_status, sales_intelligence_query                               |
| Sales-Predictor                   | FastAPI + Python, React                                  | HorecA sales forecasting                               | run_sales_forecast, get_sales_forecast_results                              |
| Ruimtemeesters-Opdrachten-Scanner | TypeScript, Playwright                                   | DAS/inhuur assignment scanning                         | search_assignments, trigger_scan                                            |
| Ruimtemeesters-Workspace          | React 19 + TS, Clerk, Radix UI                           | Team hub, notifications                                | get_notifications, get_team_info                                            |
| Ruimtemeesters-Aggregator         | Express + TS, PostgreSQL, Neo4j, Zod                     | Gateway API for cross-app queries                      | Cross-app composition tools                                                 |
