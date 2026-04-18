# Full-Stack Review, Debug & Test Round

**Date:** 2026-04-03
**Status:** Approved
**Goal:** Comprehensive quality gate across the Ruimtemeesters Browser Chatbot and all 8 MCP backend services — from infrastructure through integration testing and manual QA.

## Scope

### In scope

- Get the full stack running from zero (no prior setup)
- Resolve infrastructure conflicts (ports, networks, DB connections)
- Health-check every service
- Code review of critical integration points
- Manual testing of every assistant x tool combination
- Document all bugs found
- Produce a repeatable test runbook

### Out of scope

- CI/CD pipeline fixes (disabled lint/integration workflows)
- Performance / load testing
- Production deployment
- Writing new automated tests (gaps noted, not filled)

## Success Criteria

1. All services start cleanly and pass health checks
2. Each MCP tool is callable from the chatbot and returns valid data
3. Auth flows work (Clerk SSO or local fallback)
4. Known bugs are documented in `product-docs/20-issues/`
5. A manual test checklist exists so this can be repeated
6. Code review findings are captured and prioritized

---

## Database Multiplexing Problem

### The landscape

Six separate Postgres instances across the stack, each on a different port, plus Neo4j, Redis, and GraphDB:

| Service             | DB Type    | Host Port              | Container Port | DB Name      | Network                           |
| ------------------- | ---------- | ---------------------- | -------------- | ------------ | --------------------------------- |
| Databank            | PostgreSQL | 5432                   | 5432           | databank     | ruimtemeesters-databank-network   |
| Databank            | Neo4j      | 7687                   | 7687           | —            | ruimtemeesters-databank-network   |
| Databank            | Redis      | 6379                   | 6379           | —            | ruimtemeesters-databank-network   |
| Databank            | GraphDB    | 7200                   | 7200           | —            | ruimtemeesters-databank-network   |
| Geoportaal          | PostGIS    | 5433                   | 5432           | geoportaal   | geoportaal-network                |
| TSA                 | PostgreSQL | 6435                   | 5432           | tsa          | default + rm-network              |
| Dashboarding        | PostgreSQL | 6433                   | 5432           | dashboarding | default                           |
| Riens Sales Viewer  | PostGIS    | 5432                   | 5432           | sales_viewer | sales-viewer-network + rm-network |
| Opdrachten Scanner  | PostgreSQL | 5435                   | 5432           | cold_storage | default                           |
| Workspace           | PostgreSQL | 6432                   | 5432           | tracking     | default                           |
| Chatbot (OpenWebUI) | PostgreSQL | TBD (needs allocation) | 5432           | openwebui    | rm-network                        |

### Risks

1. **Port 5432 collision:** Databank and Riens Sales Viewer both expose host port 5432. If both start, one fails silently or steals the port. Fix: remap one (e.g., Riens to 5434).
2. **TSA/Dashboarding shared DB:** These may point at the same Postgres. Need to verify — if they do, startup order matters and migrations could conflict.
3. **Six `.env` files with `POSTGRES_PASSWORD`:** Easy to misconfigure one and get silent auth failures.
4. **Aggregator cross-DB access:** Connects directly to Databank and Geoportaal databases — needs correct host, port, and credentials for both. Uses Docker service names internally, but from host these differ.
5. **Network isolation vs reachability:** Services on different Docker networks can't see each other unless explicitly bridged. The `rm-network` is the bridge, but not all services join it.

### Resolution approach

In Phase 1, before starting any service:

1. Audit every `docker-compose.yml` for host port mappings
2. Resolve the 5432 conflict (remap Riens to 5434)
3. Verify TSA/Dashboarding DB relationship
4. Create a port allocation map and pin it in the test runbook
5. Verify all cross-service DB connections use correct Docker service names (not localhost)

---

## Phase 1: Infrastructure Layer

**Goal:** All data stores and shared infrastructure healthy, no port conflicts.

### Steps

1. **Create shared Docker network**
   - `docker network create rm-network` (if not exists)
   - Verify with `docker network ls`

2. **Audit and resolve port conflicts**
   - Extract host port mappings from every docker-compose.yml
   - Resolve Databank/Riens 5432 collision
   - Document final port allocation map

3. **Create `.env` files for every repo**
   - Copy from `.env.example` templates
   - Fill in credentials (use consistent passwords for dev)
   - Verify no hardcoded secrets in docker-compose files

4. **Start data stores (order matters)**
   - Databank infra first: Neo4j, PostgreSQL, Redis, GraphDB
   - Geoportaal: PostGIS
   - TSA: PostgreSQL
   - Dashboarding: PostgreSQL
   - Riens: PostGIS (on remapped port)
   - Opdrachten: PostgreSQL (cold storage)

5. **Health-check each data store**
   - `pg_isready` for each Postgres
   - Neo4j bolt connection test
   - Redis `PING`
   - GraphDB HTTP health endpoint

6. **Start Ollama**
   - Single instance, shared across Databank + Chatbot
   - Verify model pull works

### Deliverable

Infrastructure checklist with pass/fail per component.

---

## Phase 2: Service Layer

**Goal:** Each backend service starts, responds to health checks, basic API calls work.

### Steps per service

For each of the 8 backend services + the chatbot:

1. Start the service (Docker or local, per repo setup)
2. Hit health endpoint (or root `/` if no health check)
3. Make one representative API call
4. Check container/process logs for errors and warnings
5. Verify auth config (API key present, JWT validation if applicable)

### Service checklist

| Service             | Start method                                     | Health endpoint | Test call                  |
| ------------------- | ------------------------------------------------ | --------------- | -------------------------- |
| Databank            | `docker compose up -d backend`                   | `GET /health`   | `GET /api/documents`       |
| Geoportaal          | `docker compose up -d backend`                   | `GET /health`   | `GET /api/spatial-rules`   |
| TSA                 | `docker compose up -d tsa-engine`                | `GET /health`   | `GET /api/gemeenten`       |
| Dashboarding        | `docker compose up -d db` + local dev            | `GET /health`   | `GET /api/dashboard`       |
| Riens Sales Viewer  | `docker compose up -d`                           | `GET /health`   | `GET /api/gemeente-status` |
| Sales Predictor     | `python backend_api.py` (local)                  | `GET /health`   | `GET /api/models`          |
| Opdrachten Scanner  | local (not containerized)                        | `GET /health`   | `GET /api/inbox`           |
| Aggregator          | `docker compose up -d`                           | `GET /health`   | `GET /api/health`          |
| Chatbot (OpenWebUI) | `docker compose -f docker-compose.rm.yaml up -d` | `GET /health`   | `GET /api/config`          |

### Code review targets

- `backend/open_webui/utils/mcp/client.py` — MCP client: error handling, SSL bypass, auth forwarding
- `docker-compose.rm.yaml` — MCP server connection config, env var references
- Each service's Dockerfile — build issues, security concerns
- `.env` handling — no secrets in committed files

### Deliverable

Service health matrix (service x status x notes).

---

## Phase 3: Integration Layer

**Goal:** Full stack wired together, every tool callable from chatbot UI.

### Steps

1. **Start MCP servers**
   - `cd Ruimtemeesters-MCP-Servers && docker compose up -d`
   - Verify all 8 servers healthy on ports 3101-3108

2. **Start chatbot with MCP connections**
   - `docker compose -f docker-compose.rm.yaml up -d`
   - Verify `TOOL_SERVER_CONNECTIONS` env var is set correctly
   - Check chatbot logs for MCP tool discovery

3. **Verify tool discovery**
   - Log in to chatbot UI
   - Check that all 8 MCP servers appear in tool list
   - Verify tool count matches expectations

4. **Manual test matrix — assistant x tool**

   | Assistant                | Tools to test                                                                    | Test scenario                              |
   | ------------------------ | -------------------------------------------------------------------------------- | ------------------------------------------ |
   | Ruimtemeesters Assistant | aggregator (context_at_coordinate, search_documents, search_knowledge_graph)     | Ask for context about a known municipality |
   | Beleidsadviseur          | databank (search_beleidsdocumenten, get_knowledge_graph)                         | Search for a policy document by topic      |
   | Demografie-analist       | tsa (run_population_forecast, list_gemeenten), dashboarding (get_dashboard_data) | Request population forecast for a gemeente |
   | Ruimtelijk-adviseur      | geoportaal (query_spatial_rules, get_air_quality, get_weather)                   | Query spatial rules at a coordinate        |
   | Sales-adviseur           | riens (get_gemeente_status), sales-predictor (run_sales_forecast)                | Check contract status of a gemeente        |

5. **Auth flow testing**
   - Clerk SSO login (if configured locally)
   - Fallback auth (local account creation)
   - Verify JWT forwarding to MCP tools

6. **Error path testing**
   - Stop one MCP server, verify chatbot handles it gracefully
   - Send bad auth token, verify rejection
   - Test with non-existent tool arguments

### Deliverable

Test matrix with results, bugs filed in `product-docs/20-issues/`.

---

## Bug Tracking

All findings go to `product-docs/20-issues/` as markdown files.

### File format

```markdown
# <Title>

**Date:** YYYY-MM-DD
**Severity:** critical | high | medium | low
**Service:** <which service>
**Phase found:** 1 | 2 | 3

## Description

What's wrong.

## Repro steps

1. ...
2. ...

## Expected

What should happen.

## Actual

What actually happens.

## Notes

Any additional context, logs, screenshots.
```

### Severity guide

- **Critical:** Service won't start, data loss risk, security vulnerability
- **High:** Feature completely broken, auth bypass, wrong data returned
- **Medium:** Feature partially broken, poor error handling, misleading logs
- **Low:** Cosmetic, docs mismatch, minor inconvenience

---

## Final Deliverables

1. **Infrastructure checklist** — data stores + networks pass/fail
2. **Port allocation map** — authoritative list of which port belongs to which service
3. **Service health matrix** — each service's status after Phase 2
4. **Integration test matrix** — assistant x tool results after Phase 3
5. **Issue files** — every bug in `product-docs/20-issues/`
6. **Manual test runbook** — repeatable steps for future rounds
