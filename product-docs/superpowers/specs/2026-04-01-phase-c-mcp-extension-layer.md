# Phase C: MCP Extension Layer — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Parent spec:** `2026-03-31-browser-chatbot-design.md` — Section 9, Phase C

---

## Goal

Expose all Ruimtemeesters app capabilities as MCP (Model Context Protocol) servers so they're usable from the chatbot (OpenWebUI), Claude Code, Cursor, and any other MCP-compatible AI tool.

## Repository

**New repo:** `Ruimtemeesters-MCP-Servers` (dedicated, not in any existing repo)

**Rationale:** MCP servers are consumed by multiple clients, have their own lifecycle, and benefit from shared infrastructure (auth, schemas, types). See ADR-0004.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  MCP Clients                                          │
│  ├── OpenWebUI (chatbot.datameesters.nl)              │
│  ├── Claude Code (developer tooling)                  │
│  ├── Cursor (IDE integration)                         │
│  └── Future AI tools                                  │
└──────────────────────┬───────────────────────────────┘
                       │ MCP Protocol (stdio / SSE)
┌──────────────────────▼───────────────────────────────┐
│  Ruimtemeesters-MCP-Servers                           │
│                                                       │
│  packages/shared/       — Auth, Zod schemas, types    │
│  packages/databank/     — 5 tools (search, KG, etc.)  │
│  packages/geoportaal/   — 6 tools (rules, air, etc.)  │
│  packages/tsa/          — 6 tools (forecast, etc.)    │
│  packages/dashboarding/ — 4 tools (data, stats, etc.) │
│  packages/riens/        — 2 tools (status, update)    │
│  packages/sales-predictor/ — 4 tools                  │
│  packages/opdrachten/   — 7 tools (inbox, pipeline)   │
│  packages/aggregator/   — 12 tools (context, KG, etc.)│
└──────────────────────┬───────────────────────────────┘
                       │ HTTP (REST API calls)
┌──────────────────────▼───────────────────────────────┐
│  Existing Apps (unchanged)                            │
│  Databank, Geoportaal, TSA, Dashboarding, Riens,      │
│  Sales Predictor, Opdrachten Scanner, Aggregator      │
└──────────────────────────────────────────────────────┘
```

## Tech Stack

- **Language:** TypeScript (matches RM ecosystem)
- **MCP SDK:** `@modelcontextprotocol/sdk`
- **HTTP Client:** Native fetch or `undici`
- **Schema Validation:** Zod (reuse patterns from Aggregator)
- **Package Manager:** pnpm (workspace)
- **Build:** tsx for dev, tsup for production
- **Transport:** stdio (for Claude Code/Cursor) + SSE (for OpenWebUI)

## Repo Structure

```
Ruimtemeesters-MCP-Servers/
├── packages/
│   ├── shared/
│   │   ├── src/
│   │   │   ├── auth.ts          # Clerk JWT validation + API key auth
│   │   │   ├── http.ts          # Shared HTTP client with error handling
│   │   │   ├── schemas.ts       # Common Zod schemas (gemeente code, bbox, etc.)
│   │   │   └── index.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── databank/
│   │   ├── src/
│   │   │   ├── server.ts        # MCP server entry point
│   │   │   └── tools.ts         # Tool definitions
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── geoportaal/              # Same structure
│   ├── tsa/
│   ├── dashboarding/
│   ├── riens/
│   ├── sales-predictor/
│   ├── opdrachten/
│   └── aggregator/
├── docker-compose.yaml          # Run all MCP servers
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── .env.example
└── README.md
```

## Tool Mapping

Each MCP server exposes the same tools as the Phase A OpenWebUI Tools, but via MCP protocol. The tool names, parameters, and descriptions are identical.

| MCP Server      | Tools                                                                                                                                                                                                   | Source (Phase A)            |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| databank        | search_beleidsdocumenten, get_knowledge_graph, get_document, list_queries, create_query                                                                                                                 | rm-tools/databank.py        |
| geoportaal      | query_spatial_rules, get_air_quality, get_weather, get_building_data, search_documents, search_pdok                                                                                                     | rm-tools/geoportaal.py      |
| tsa             | run_population_forecast, get_forecast_results, run_backtest, get_diagnostics, list_gemeenten, get_model_status                                                                                          | rm-tools/tsa.py             |
| dashboarding    | get_dashboard_data, get_statistics, get_trends, search_dashboard                                                                                                                                        | rm-tools/dashboarding.py    |
| riens           | get_gemeente_status, update_gemeente                                                                                                                                                                    | rm-tools/riens.py           |
| sales-predictor | run_sales_forecast, get_predictions, compare_models, list_models                                                                                                                                        | rm-tools/sales_predictor.py |
| opdrachten      | get_inbox, get_pipeline, get_pipeline_deadlines, search_library, get_stats, accept_inbox_item, move_pipeline_stage                                                                                      | rm-tools/opdrachten.py      |
| aggregator      | context_at_coordinate, context_municipality, search_documents, get_document_summary, spatial_rules_at_point, solar_potential, search_knowledge_graph, get_entity_relations, traverse_graph, graph_stats | rm-tools/aggregator.py      |

## Auth

Two auth modes (configurable per server):

1. **API Key** — for app-to-app calls (TSA, Aggregator use this)
2. **Clerk JWT** — for user-context calls (forwarded from MCP client)

The shared auth module validates both.

## Transport Modes

- **stdio** — for local use with Claude Code and Cursor (default)
- **SSE** — for remote use from OpenWebUI via HTTP

Each server supports both; the mode is selected via CLI flag or env var.

## Phase Dependencies

```
C1 (shared infra) → C2 (per-app servers) → C3 (aggregator) → C4 (OpenWebUI client) → C5 (external consumers)
```

C1 and C2 can be developed together (shared evolves as servers are built).
C4 depends on OpenWebUI's MCP client support (check current fork capabilities).
C5 is config/docs only — no code needed beyond what C2/C3 produce.

## Phasing

### C1: Shared Infrastructure

- pnpm workspace setup
- Shared auth, HTTP client, Zod schemas
- MCP server template (copy-paste starting point)

### C2: Per-App MCP Servers (7 servers)

- One server per app, same tools as Phase A
- Each server is independently runnable

### C3: Aggregator MCP Server

- Wraps all Aggregator endpoints
- Zod schemas match Aggregator's existing validation

### C4: OpenWebUI MCP Client

- Configure OpenWebUI fork to connect to MCP servers
- May require fork changes for MCP client support
- Migrate Phase A Python tools to MCP client calls (or keep both)

### C5: External Consumers

- Claude Code config (`.claude.json` or `claude_desktop_config.json`)
- Cursor config
- Developer documentation
