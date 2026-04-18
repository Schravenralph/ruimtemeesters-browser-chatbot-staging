# Full-Stack Review, Debug & Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the entire Ruimtemeesters stack running from zero, smoke-test every service, then manually test every assistant x tool combination through the chatbot UI.

**Architecture:** Layered bring-up: infrastructure (networks, databases, Ollama) -> backend services -> MCP servers -> chatbot. Each layer is verified before proceeding to the next.

**Tech Stack:** Docker Compose, PostgreSQL, PostGIS, Neo4j, Redis, GraphDB, Ollama, Node.js, Python/FastAPI, pnpm, SvelteKit

---

## Port Allocation Map (Reference)

This is the authoritative port map. All .env files must match these values.

| Service                     | Host Port | Protocol | Notes                          |
| --------------------------- | --------- | -------- | ------------------------------ |
| Databank Backend            | 4000      | HTTP     | 127.0.0.1 only                 |
| Databank Frontend           | 5173      | HTTP     | 127.0.0.1 only                 |
| Databank PostgreSQL         | 5432      | TCP      | 127.0.0.1 only                 |
| Databank Neo4j (bolt)       | 7687      | TCP      | internal                       |
| Databank Neo4j (http)       | 7474      | HTTP     | internal                       |
| Databank Redis              | 6379      | TCP      | internal                       |
| Databank GraphDB            | 7200      | HTTP     | 127.0.0.1 only                 |
| Geoportaal Backend          | 5002      | HTTP     | maps to container port 5000    |
| Geoportaal Frontend         | 3000      | HTTP     |                                |
| Geoportaal PostGIS          | 5433      | TCP      |                                |
| Geoportaal GeoNode          | 8001      | HTTP     | maps to container port 8000    |
| TSA Engine                  | 8100      | HTTP     |                                |
| TSA PostgreSQL              | 6435      | TCP      | DB name: dashboarding (shared) |
| Dashboarding PostgreSQL     | 6433      | TCP      | DB name: dashboarding          |
| Dashboarding App            | 5022      | HTTP     | run locally, not containerized |
| Riens Sales Viewer DB       | 5434      | TCP      | remapped from default 5432     |
| Riens Sales Viewer API      | 3001      | HTTP     | on rm-network                  |
| Riens Sales Viewer Frontend | 5176      | HTTP     |                                |
| Sales Predictor API         | 8000      | HTTP     | run locally, not containerized |
| Opdrachten Scanner API      | 6300      | HTTP     | run locally, not containerized |
| Opdrachten Cold Postgres    | 5435      | TCP      |                                |
| Aggregator                  | 6000      | HTTP     | on rm-network                  |
| MCP Databank                | 3101      | HTTP     | internal to rm-network         |
| MCP Geoportaal              | 3102      | HTTP     | internal to rm-network         |
| MCP TSA                     | 3103      | HTTP     | internal to rm-network         |
| MCP Dashboarding            | 3104      | HTTP     | internal to rm-network         |
| MCP Riens                   | 3105      | HTTP     | internal to rm-network         |
| MCP Sales Predictor         | 3106      | HTTP     | internal to rm-network         |
| MCP Opdrachten              | 3107      | HTTP     | internal to rm-network         |
| MCP Aggregator              | 3108      | HTTP     | internal to rm-network         |
| Chatbot (OpenWebUI)         | 3333      | HTTP     |                                |
| Chatbot Ollama              | —         | HTTP     | internal to rm-internal        |
| Chatbot PostgreSQL          | —         | TCP      | internal to rm-internal        |

---

## Phase 1: Infrastructure Layer

### Task 1: Create Docker Networks

**Files:**

- Reference: `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/docker-compose.rm.yaml`
- Reference: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/docker-compose.yaml`
- Reference: `/home/ralph/Projects/Ruimtemeesters-Databank/docker-compose.yml`

- [ ] **Step 1: Check existing Docker networks**

```bash
docker network ls --format '{{.Name}}'
```

Expected: list of current networks (probably just default bridge/host/none).

- [ ] **Step 2: Create rm-network**

```bash
docker network create rm-network
```

Expected: network ID hash printed. This is the shared network connecting chatbot, MCP servers, and some backend services.

- [ ] **Step 3: Verify**

```bash
docker network ls | grep rm-network
```

Expected: `rm-network` appears with `bridge` driver.

Note: Other networks (`ruimtemeesters-databank-network`, `geoportaal-network`, `sales-viewer-network`) are created automatically by their respective docker-compose files. `rm-network` is the only one that must exist beforehand because it's declared `external: true`.

---

### Task 2: Set Up Databank Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-Databank/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
cp .env.example .env
```

- [ ] **Step 2: Set required passwords in .env**

Edit `.env` and set these values (use simple dev passwords):

```
NEO4J_PASSWORD=dev_neo4j_2026
GRAPHDB_PASSWORD=dev_graphdb_2026
POSTGRES_PASSWORD=dev_postgres_2026
REDIS_PASSWORD=dev_redis_2026
JWT_SECRET=dev_jwt_secret_2026
```

Leave `OPENAI_API_KEY` and `OPENROUTER_API_KEY` empty — we're using Ollama instead.

Set Ollama config:

```
OLLAMA_API_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2
```

- [ ] **Step 3: Verify no port conflicts in docker-compose.yml**

```bash
grep -n "ports:" -A 2 /home/ralph/Projects/Ruimtemeesters-Databank/docker-compose.yml
```

Confirm Databank Postgres is on `127.0.0.1:5432:5432`. This is fine because it's localhost-only and Riens is remapped to 5434.

---

### Task 3: Set Up Geoportaal Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-Geoportaal/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Geoportaal
cp .env.example .env
```

- [ ] **Step 2: Set required values in .env**

```
POSTGRES_PASSWORD=dev_geoportaal_2026
BELEIDSSCAN_API_URL=http://host.docker.internal:4000
BELEIDSSCAN_API_KEY=dev_databank_key_2026
```

- [ ] **Step 3: Verify PostGIS port is 5433 (no conflict with Databank's 5432)**

```bash
grep -n "5433" /home/ralph/Projects/Ruimtemeesters-Geoportaal/docker-compose.yml
```

Expected: `"5433:5432"` mapping confirmed.

---

### Task 4: Set Up TSA Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-TSA/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-TSA
cp .env.example .env
```

- [ ] **Step 2: Set required values**

```
DB_PASSWORD=dev_postgres_2026
TSA_API_KEY=dev_tsa_key_2026
```

- [ ] **Step 3: Verify TSA uses DB name "dashboarding" and port 6435**

```bash
grep -n "DB_NAME\|POSTGRES_PORT\|6435" /home/ralph/Projects/Ruimtemeesters-TSA/docker-compose.yml
```

Note: TSA and Dashboarding share the same DB name (`dashboarding`). TSA's Postgres is on host port 6435, Dashboarding's is on 6433. These are **separate instances** with the same schema — verify during Phase 2 whether TSA actually needs Dashboarding's data or has its own copy.

---

### Task 5: Set Up Dashboarding Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-Dashboarding/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Dashboarding
cp .env.example .env
```

- [ ] **Step 2: Set required values**

```
DB_PASSWORD=postgres
JWT_SECRET=dev_jwt_secret_2026
DATABASE_URL=postgresql://postgres:postgres@localhost:6433/dashboarding
DB_PORT=6433
```

**Bug found:** The `.env.example` has `DB_PORT=6432` but docker-compose exposes `6433:5432`. This is a mismatch. Fix the .env to use `6433` and update `DATABASE_URL` to match.

- [ ] **Step 3: Verify the port mismatch**

```bash
grep -n "6432\|6433" /home/ralph/Projects/Ruimtemeesters-Dashboarding/docker-compose.yml
grep -n "6432\|6433" /home/ralph/Projects/Ruimtemeesters-Dashboarding/.env.example
```

If docker-compose says `6433` and .env.example says `6432`, file an issue.

---

### Task 6: Set Up Riens Sales Viewer Environment

**Files:**

- Check: `/home/ralph/Projects/Riens-Sales-Viewer/.env` (already exists with real values)

- [ ] **Step 1: Verify .env exists and has correct port**

```bash
grep "POSTGRES_PORT" /home/ralph/Projects/Riens-Sales-Viewer/.env
```

Expected: `POSTGRES_PORT=5434` (already remapped from default 5432 to avoid conflict with Databank).

- [ ] **Step 2: Verify docker-compose uses the env var for port mapping**

```bash
grep -n "5432\|POSTGRES_PORT" /home/ralph/Projects/Riens-Sales-Viewer/docker-compose.yml
```

Confirm the port mapping uses `${POSTGRES_PORT:-5432}:5432` or similar, so our .env override works.

- [ ] **Step 3: Verify API key is set**

```bash
grep "SERVICE_API_KEY" /home/ralph/Projects/Riens-Sales-Viewer/.env
```

Expected: `SERVICE_API_KEY=rm-riens-service-2026` (already set).

---

### Task 7: Set Up Sales Predictor Environment

**Files:**

- Copy: `/home/ralph/Projects/Sales-Predictor/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Sales-Predictor
cp .env.example .env
```

- [ ] **Step 2: Set required values**

```
SERVICE_API_KEY=dev_sales_predictor_key_2026
```

The `OPENWEATHER_API_KEY` can be left empty for now — it's only needed for weather-based predictions.

---

### Task 8: Set Up Opdrachten Scanner Environment

**Files:**

- Check: `/home/ralph/Projects/Ruimtemeesters-Opdrachten-Scanner/.env`

- [ ] **Step 1: Verify .env exists**

```bash
ls -la /home/ralph/Projects/Ruimtemeesters-Opdrachten-Scanner/.env
```

- [ ] **Step 2: Verify key values**

```bash
grep "API_PORT\|SERVICE_API_KEY\|DATABASE_URL" /home/ralph/Projects/Ruimtemeesters-Opdrachten-Scanner/.env
```

Expected:

- `API_PORT=6300`
- `SERVICE_API_KEY=rm-opdrachten-service-2026`
- `DATABASE_URL=postgres://tracking:tracking@localhost:6432/opdrachten`

Note: The DATABASE_URL points to port 6432 which is the Workspace Postgres. Verify this is intentional during Phase 2.

---

### Task 9: Set Up Aggregator Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-Aggregator/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
cp .env.example .env
```

- [ ] **Step 2: Set required values**

```
PORT=6000
API_KEY=dev_aggregator_key_2026
DATABANK_DB_HOST=ruimtemeesters-databank-postgres
DATABANK_DB_PORT=5432
DATABANK_DB_NAME=beleidsscan
DATABANK_DB_USER=postgres
DATABANK_DB_PASSWORD=dev_postgres_2026
GEOPORTAAL_DB_HOST=geoportaal-postgis
GEOPORTAAL_DB_PORT=5432
GEOPORTAAL_DB_NAME=geoportaal
GEOPORTAAL_DB_USER=geoportaal_user
GEOPORTAAL_DB_PASSWORD=dev_geoportaal_2026
```

Note: DB hosts use Docker container names because Aggregator runs on the same Docker networks as Databank and Geoportaal. Container port is 5432 (not the host-mapped ports).

---

### Task 10: Set Up MCP Servers Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/.env.example` -> `.env`

- [ ] **Step 1: Copy .env.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
cp .env.example .env
```

- [ ] **Step 2: Set API keys matching the backend services**

```
DATABANK_API_URL=http://ruimtemeesters-databank-backend:4000
GEOPORTAAL_API_URL=http://host.docker.internal:5002
TSA_API_URL=http://host.docker.internal:8100
DASHBOARDING_API_URL=http://host.docker.internal:5022
RIENS_API_URL=http://sales-viewer-api:3001
SALES_PREDICTOR_API_URL=http://host.docker.internal:8000
OPDRACHTEN_API_URL=http://host.docker.internal:6300
AGGREGATOR_API_URL=http://ruimtemeesters-aggregator:6000

DATABANK_AUTH_TOKEN=dev_databank_key_2026
GEOPORTAAL_API_KEY=dev_geoportaal_key_2026
TSA_API_KEY=dev_tsa_key_2026
DASHBOARDING_API_KEY=dev_dashboarding_key_2026
RIENS_API_KEY=rm-riens-service-2026
SALES_PREDICTOR_API_KEY=dev_sales_predictor_key_2026
OPDRACHTEN_API_KEY=rm-opdrachten-service-2026
AGGREGATOR_API_KEY=dev_aggregator_key_2026
```

Note: URLs use Docker container names for services on rm-network (Databank, Riens, Aggregator) and `host.docker.internal` for services running on the host (Geoportaal, TSA, Dashboarding, Sales Predictor, Opdrachten).

---

### Task 11: Set Up Chatbot Environment

**Files:**

- Copy: `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/.env.rm.example` -> `.env`

- [ ] **Step 1: Copy .env.rm.example to .env**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
cp .env.rm.example .env
```

- [ ] **Step 2: Set required values**

```
POSTGRES_USER=rmchatbot
POSTGRES_PASSWORD=dev_rmchatbot_2026
POSTGRES_DB=rmchatbot

OPEN_WEBUI_PORT=3333

# MCP API keys (must match MCP server .env values)
DATABANK_AUTH_TOKEN=dev_databank_key_2026
GEOPORTAAL_API_KEY=dev_geoportaal_key_2026
TSA_API_KEY=dev_tsa_key_2026
DASHBOARDING_API_KEY=dev_dashboarding_key_2026
RIENS_API_KEY=rm-riens-service-2026
SALES_PREDICTOR_API_KEY=dev_sales_predictor_key_2026
OPDRACHTEN_API_KEY=rm-opdrachten-service-2026
AGGREGATOR_API_KEY=dev_aggregator_key_2026
```

Leave Clerk OIDC vars empty for now — we'll test with local auth first.

- [ ] **Step 3: Verify TOOL_SERVER_CONNECTIONS in docker-compose.rm.yaml**

```bash
grep -c "rm-mcp" /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/docker-compose.rm.yaml
```

Expected: 8 occurrences (one per MCP server).

---

### Task 12: Start Databank Infrastructure

**Files:**

- Run: `/home/ralph/Projects/Ruimtemeesters-Databank/docker-compose.yml`

- [ ] **Step 1: Start Databank data stores (no backend yet)**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
docker compose up -d postgres neo4j redis graphdb cold-postgres
```

- [ ] **Step 2: Wait for health checks**

```bash
docker compose ps
```

Expected: all 5 services show `healthy` or `running`.

- [ ] **Step 3: Verify Postgres is accepting connections**

```bash
docker exec ruimtemeesters-databank-postgres pg_isready -U postgres
```

Expected: `accepting connections`

- [ ] **Step 4: Verify Neo4j is accepting connections**

```bash
docker exec ruimtemeesters-databank-neo4j cypher-shell -u neo4j -p dev_neo4j_2026 "RETURN 1"
```

Expected: returns `1`.

- [ ] **Step 5: Verify Redis is accepting connections**

```bash
docker exec ruimtemeesters-databank-redis redis-cli -a dev_redis_2026 PING
```

Expected: `PONG`

- [ ] **Step 6: Verify GraphDB is accepting connections**

```bash
curl -s http://localhost:7200/rest/repositories
```

Expected: JSON array (possibly empty).

---

### Task 13: Start Geoportaal Infrastructure

**Files:**

- Run: `/home/ralph/Projects/Ruimtemeesters-Geoportaal/docker-compose.yml`

- [ ] **Step 1: Start PostGIS only**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Geoportaal
docker compose up -d postgis
```

- [ ] **Step 2: Verify PostGIS is accepting connections**

```bash
docker exec geoportaal-postgis pg_isready -U geoportaal_user -d geoportaal
```

Expected: `accepting connections`

- [ ] **Step 3: Verify port 5433 is in use (not conflicting)**

```bash
ss -tlnp | grep 5433
```

Expected: one listener on port 5433.

---

### Task 14: Start TSA & Dashboarding Databases

- [ ] **Step 1: Start TSA Postgres**

```bash
cd /home/ralph/Projects/Ruimtemeesters-TSA
docker compose up -d postgres
```

- [ ] **Step 2: Verify TSA Postgres on port 6435**

```bash
docker compose ps
ss -tlnp | grep 6435
```

- [ ] **Step 3: Start Dashboarding Postgres**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Dashboarding
docker compose up -d db
```

- [ ] **Step 4: Verify Dashboarding Postgres on port 6433**

```bash
docker compose ps
ss -tlnp | grep 6433
```

- [ ] **Step 5: Investigate TSA/Dashboarding DB relationship**

Check if TSA's DB has the same schema as Dashboarding's:

```bash
docker exec -it $(docker ps -qf "name=dashboarding-postgres") psql -U postgres -d dashboarding -c "\dt"
```

Then compare with TSA's:

```bash
PGPASSWORD=dev_postgres_2026 psql -h localhost -p 6435 -U postgres -d dashboarding -c "\dt"
```

Document whether these are truly independent or need to share data. File an issue if unclear.

---

### Task 15: Start Riens & Opdrachten Databases

- [ ] **Step 1: Start Riens PostGIS**

```bash
cd /home/ralph/Projects/Riens-Sales-Viewer
docker compose up -d db
```

- [ ] **Step 2: Verify Riens DB on port 5434 (not 5432)**

```bash
ss -tlnp | grep 5434
```

If it's on 5432 instead, the .env override isn't working. Check `docker-compose.yml` for how the port is mapped.

- [ ] **Step 3: Start Opdrachten cold storage Postgres**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Opdrachten-Scanner
docker compose up -d cold-postgres
```

- [ ] **Step 4: Verify on port 5435**

```bash
ss -tlnp | grep 5435
```

---

### Task 16: Start Ollama and Pull a Model

- [ ] **Step 1: Check if Ollama is already running on host**

```bash
curl -s http://localhost:11434/api/tags 2>/dev/null || echo "not running"
```

- [ ] **Step 2: If not running, start via Databank's docker-compose**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
docker compose --profile llm up -d ollama
```

Or if Ollama is installed locally:

```bash
ollama serve &
```

- [ ] **Step 3: Pull a lightweight model for testing**

```bash
ollama pull llama3.2
```

Expected: model downloads and becomes available.

- [ ] **Step 4: Verify model is available**

```bash
ollama list
```

Expected: `llama3.2` appears in list.

---

### Task 17: Infrastructure Health Summary

- [ ] **Step 1: Run full port scan to verify no conflicts**

```bash
ss -tlnp | grep -E '(4000|5002|5173|3000|5432|5433|5434|5435|6432|6433|6435|7200|7687|6379|8001|8100|3001|5176|8000|6300|6000|3333|11434|310[1-8])' | sort -t: -k2 -n
```

Expected: each port appears exactly once.

- [ ] **Step 2: Verify all Docker containers are running**

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | sort
```

Expected: all data store containers running with correct port mappings.

- [ ] **Step 3: Document any issues found**

Create issue files in `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/product-docs/20-issues/` for any problems found during Phase 1.

- [ ] **Step 4: Commit infrastructure findings**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
git add product-docs/20-issues/
git commit -m "docs: Phase 1 infrastructure issues from full-stack test round"
```

---

## Phase 2: Service Layer

### Task 18: Start and Verify Databank Backend

**Files:**

- Reference: `/home/ralph/Projects/Ruimtemeesters-Databank/docker-compose.yml`

- [ ] **Step 1: Start Databank backend**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Databank
docker compose up -d backend
```

- [ ] **Step 2: Wait for it to be healthy and check logs**

```bash
docker compose logs backend --tail 50
```

Look for: startup messages, database connection success, any errors.

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:4000/health | head -20
```

Expected: 200 OK with health status JSON.

- [ ] **Step 4: Test a basic API call**

```bash
curl -s http://localhost:4000/api/documents | head -20
```

Expected: JSON response (possibly empty array if no data seeded).

- [ ] **Step 5: Check if backend is reachable from rm-network**

```bash
docker run --rm --network rm-network curlimages/curl curl -s http://ruimtemeesters-databank-backend:4000/health
```

Expected: same health response. This is how MCP servers will reach it.

---

### Task 19: Start and Verify Geoportaal Backend

- [ ] **Step 1: Start Geoportaal backend + GeoNode**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Geoportaal
docker compose up -d backend geonode
```

- [ ] **Step 2: Check logs**

```bash
docker compose logs backend --tail 50
```

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:5002/health | head -20
```

Expected: 200 OK.

- [ ] **Step 4: Test basic API call**

```bash
curl -s http://localhost:5002/api/spatial-rules | head -20
```

- [ ] **Step 5: Verify GeoNode is running**

```bash
curl -s http://localhost:8001/ | head -5
```

---

### Task 20: Start and Verify TSA Engine

- [ ] **Step 1: Start TSA engine**

```bash
cd /home/ralph/Projects/Ruimtemeesters-TSA
docker compose up -d tsa-engine
```

- [ ] **Step 2: Check logs**

```bash
docker compose logs tsa-engine --tail 50
```

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:8100/health | head -20
```

- [ ] **Step 4: Test list gemeenten**

```bash
curl -s -H "X-API-Key: dev_tsa_key_2026" http://localhost:8100/api/v1/gemeenten | head -20
```

Expected: JSON list of municipalities.

---

### Task 21: Start and Verify Dashboarding

- [ ] **Step 1: Check how to run the Dashboarding app locally**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Dashboarding
cat package.json | grep -A 10 '"scripts"'
```

- [ ] **Step 2: Install dependencies and start**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Dashboarding
npm install
npm run dev
```

Expected: SvelteKit dev server starts on port 5022.

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:5022/health | head -20
```

- [ ] **Step 4: If no /health endpoint, test root or API**

```bash
curl -s http://localhost:5022/ | head -20
curl -s http://localhost:5022/api | head -20
```

---

### Task 22: Start and Verify Riens Sales Viewer

- [ ] **Step 1: Start Riens API + frontend**

```bash
cd /home/ralph/Projects/Riens-Sales-Viewer
docker compose up -d api frontend
```

- [ ] **Step 2: Check logs**

```bash
docker compose logs api --tail 50
```

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:3001/health | head -20
```

- [ ] **Step 4: Test API with auth**

```bash
curl -s -H "X-API-Key: rm-riens-service-2026" http://localhost:3001/api/gemeente-status | head -20
```

- [ ] **Step 5: Verify API is reachable on rm-network**

```bash
docker run --rm --network rm-network curlimages/curl curl -s http://sales-viewer-api:3001/health
```

---

### Task 23: Start and Verify Sales Predictor

- [ ] **Step 1: Check Python dependencies**

```bash
cd /home/ralph/Projects/Sales-Predictor
cat requirements.txt 2>/dev/null || cat pyproject.toml | head -40
```

- [ ] **Step 2: Install and start**

```bash
cd /home/ralph/Projects/Sales-Predictor
pip install -r requirements.txt 2>/dev/null || pip install -e .
python backend_api.py &
```

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:8000/health | head -20
```

- [ ] **Step 4: Test API with auth**

```bash
curl -s -H "X-API-Key: dev_sales_predictor_key_2026" http://localhost:8000/api/models | head -20
```

---

### Task 24: Start and Verify Opdrachten Scanner

- [ ] **Step 1: Check how to run locally**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Opdrachten-Scanner
cat package.json | grep -A 10 '"scripts"'
```

- [ ] **Step 2: Install and start**

```bash
npm install
npm run dev
```

Expected: server starts on port 6300.

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:6300/health | head -20
```

- [ ] **Step 4: Test API with auth**

```bash
curl -s -H "X-API-Key: rm-opdrachten-service-2026" http://localhost:6300/api/inbox | head -20
```

---

### Task 25: Start and Verify Aggregator

- [ ] **Step 1: Start Aggregator**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Aggregator
docker compose up -d
```

- [ ] **Step 2: Check logs**

```bash
docker compose logs aggregator --tail 50
```

- [ ] **Step 3: Test health endpoint**

```bash
curl -s http://localhost:6000/health | head -20
```

- [ ] **Step 4: Test basic API call**

```bash
curl -s -H "X-API-Key: dev_aggregator_key_2026" http://localhost:6000/api/health | head -20
```

- [ ] **Step 5: Verify reachable from rm-network**

```bash
docker run --rm --network rm-network curlimages/curl curl -s http://ruimtemeesters-aggregator:6000/health
```

---

### Task 26: Code Review — MCP Client

**Files:**

- Review: `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/backend/open_webui/utils/mcp/client.py`

- [ ] **Step 1: Read the MCP client code**

Read the full file. Look for:

- Error handling when MCP server is unreachable
- SSL verification bypass logic (security concern)
- Auth header forwarding
- Timeout configuration
- Connection retry behavior

- [ ] **Step 2: Read the MCP config in main.py or config.py**

```bash
grep -n "TOOL_SERVER\|mcp" /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/backend/open_webui/config.py | head -20
grep -n "TOOL_SERVER\|mcp" /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/backend/open_webui/main.py | head -20
```

- [ ] **Step 3: Document findings**

Create code review notes in `product-docs/20-issues/` for anything concerning.

---

### Task 27: Service Health Summary

- [ ] **Step 1: Test all services in one sweep**

```bash
echo "=== Databank ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:4000/health
echo "=== Geoportaal ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:5002/health
echo "=== TSA ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/health
echo "=== Dashboarding ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:5022/health
echo "=== Riens ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/health
echo "=== Sales Predictor ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
echo "=== Opdrachten ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:6300/health
echo "=== Aggregator ===" && curl -s -o /dev/null -w "%{http_code}" http://localhost:6000/health
```

Expected: all return `200`.

- [ ] **Step 2: Document Phase 2 issues**

File issues for any services that failed to start or respond.

- [ ] **Step 3: Commit Phase 2 findings**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
git add product-docs/20-issues/
git commit -m "docs: Phase 2 service layer issues from full-stack test round"
```

---

## Phase 3: Integration Layer

### Task 28: Start MCP Servers

**Files:**

- Run: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/docker-compose.yaml`

- [ ] **Step 1: Install pnpm dependencies (needed for Docker build)**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
pnpm install
```

- [ ] **Step 2: Start all 8 MCP server containers**

```bash
docker compose up -d --build
```

- [ ] **Step 3: Verify all 8 are healthy**

```bash
docker compose ps
```

Expected: 8 containers, all healthy.

- [ ] **Step 4: Test each MCP server's health endpoint from inside the network**

```bash
for port in 3101 3102 3103 3104 3105 3106 3107 3108; do
  echo "=== MCP port $port ==="
  docker run --rm --network rm-network curlimages/curl curl -s http://rm-mcp-$([ $port -eq 3101 ] && echo databank || [ $port -eq 3102 ] && echo geoportaal || [ $port -eq 3103 ] && echo tsa || [ $port -eq 3104 ] && echo dashboarding || [ $port -eq 3105 ] && echo riens || [ $port -eq 3106 ] && echo sales-predictor || [ $port -eq 3107 ] && echo opdrachten || echo aggregator):$port/health
done
```

Or simpler — check docker compose logs for all:

```bash
docker compose logs --tail 10
```

Look for: "MCP server started on port XXXX" messages from each.

---

### Task 29: Start Chatbot

**Files:**

- Run: `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/docker-compose.rm.yaml`

- [ ] **Step 1: Build and start the chatbot**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
docker compose -f docker-compose.rm.yaml up -d --build
```

This starts: rm-chatbot (OpenWebUI), rm-ollama, rm-chatbot-db (Postgres).

- [ ] **Step 2: Wait for startup (can take 1-2 minutes for first build)**

```bash
docker compose -f docker-compose.rm.yaml logs rm-chatbot --tail 30
```

Look for: "Application startup complete" or similar.

- [ ] **Step 3: Test chatbot health**

```bash
curl -s http://localhost:3333/health | head -20
```

Expected: 200 OK.

- [ ] **Step 4: Open in browser**

Open `http://localhost:3333` in a web browser. You should see the OpenWebUI login page.

- [ ] **Step 5: Create a local admin account**

Since Clerk is not configured, create a local account through the UI:

1. Click "Sign Up"
2. Enter name, email, password
3. First account becomes admin automatically

---

### Task 30: Verify MCP Tool Discovery

- [ ] **Step 1: Check chatbot logs for MCP tool registration**

```bash
docker compose -f docker-compose.rm.yaml logs rm-chatbot 2>&1 | grep -i "tool\|mcp\|server" | tail -30
```

Look for: tool discovery messages mentioning all 8 MCP servers.

- [ ] **Step 2: Check tools in the UI**

1. Log in to `http://localhost:3333`
2. Go to Admin Panel > Settings > Tools (or Workspace > Tools)
3. Verify all 8 MCP servers appear with their tools listed

- [ ] **Step 3: If tools don't appear, check TOOL_SERVER_CONNECTIONS**

```bash
docker compose -f docker-compose.rm.yaml exec rm-chatbot env | grep TOOL_SERVER
```

Verify the JSON is properly formatted and all 8 servers are listed.

- [ ] **Step 4: If MCP servers are unreachable, test network connectivity**

```bash
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-databank:3101/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-geoportaal:3102/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-tsa:3103/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-dashboarding:3104/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-riens:3105/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-sales-predictor:3106/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-opdrachten:3107/health
docker compose -f docker-compose.rm.yaml exec rm-chatbot curl -s http://rm-mcp-aggregator:3108/health
```

---

### Task 31: Configure Ollama Model in Chatbot

- [ ] **Step 1: Verify Ollama has a model available inside the chatbot's network**

```bash
docker compose -f docker-compose.rm.yaml exec rm-ollama ollama list
```

If empty, pull a model:

```bash
docker compose -f docker-compose.rm.yaml exec rm-ollama ollama pull llama3.2
```

- [ ] **Step 2: Configure the model in OpenWebUI**

1. Go to Admin Panel > Settings > Connections
2. Verify Ollama URL is `http://ollama:11434`
3. Click refresh — `llama3.2` should appear
4. Set as default model

---

### Task 32: Register Assistants

**Files:**

- Run: `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/rm-tools/register_assistants.py`

- [ ] **Step 1: Check what the script needs**

```bash
head -50 /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot/rm-tools/register_assistants.py
```

- [ ] **Step 2: Get admin JWT token**

After logging in to the chatbot UI, get the JWT from browser:

1. Open browser DevTools > Application > Cookies
2. Copy the `token` cookie value

Or check if there's an API endpoint:

```bash
curl -s -X POST http://localhost:3333/api/v1/auths/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@example.com","password":"your-password"}' | head -20
```

- [ ] **Step 3: Run the assistant registration script**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
python rm-tools/register_assistants.py --url http://localhost:3333 --token <JWT_TOKEN>
```

Expected: 5 assistants + 8 prompt templates registered.

- [ ] **Step 4: Verify assistants appear in the UI**

In the chatbot, click the model dropdown. You should see:

- Ruimtemeesters Assistant
- Beleidsadviseur
- Demografie-analist
- Ruimtelijk-adviseur
- Sales-adviseur

---

### Task 33: Manual Test — Ruimtemeesters Assistant (Aggregator)

- [ ] **Step 1: Select "Ruimtemeesters Assistant" in the chatbot**

- [ ] **Step 2: Test context_at_coordinate**

Send: "Geef me context over de gemeente Amsterdam" or "Wat is de context bij coördinaat 52.3676, 4.9041?"

Expected: The assistant calls the aggregator tool and returns spatial/document context.

- [ ] **Step 3: Test search_documents**

Send: "Zoek documenten over woningbouw"

Expected: Returns relevant documents from the aggregator.

- [ ] **Step 4: Test search_knowledge_graph**

Send: "Wat weet je over het bestemmingsplan van Utrecht?"

Expected: Returns knowledge graph results.

- [ ] **Step 5: Document results**

Note what worked, what failed, error messages. File issues for failures.

---

### Task 34: Manual Test — Beleidsadviseur (Databank)

- [ ] **Step 1: Select "Beleidsadviseur" in the chatbot**

- [ ] **Step 2: Test search_beleidsdocumenten**

Send: "Zoek beleidsdocumenten over energietransitie"

- [ ] **Step 3: Test get_knowledge_graph**

Send: "Laat me de kennisgraaf zien over woningbouw"

- [ ] **Step 4: Document results**

---

### Task 35: Manual Test — Demografie-analist (TSA + Dashboarding)

- [ ] **Step 1: Select "Demografie-analist" in the chatbot**

- [ ] **Step 2: Test list_gemeenten (TSA)**

Send: "Welke gemeenten kun je analyseren?"

- [ ] **Step 3: Test run_population_forecast (TSA)**

Send: "Maak een bevolkingsprognose voor gemeente Eindhoven"

- [ ] **Step 4: Test get_dashboard_data (Dashboarding)**

Send: "Geef me demografische data van Rotterdam"

- [ ] **Step 5: Document results**

---

### Task 36: Manual Test — Ruimtelijk-adviseur (Geoportaal)

- [ ] **Step 1: Select "Ruimtelijk-adviseur" in the chatbot**

- [ ] **Step 2: Test query_spatial_rules**

Send: "Wat zijn de bestemmingsplanregels op locatie 52.0907, 5.1214?" (Utrecht coordinates)

- [ ] **Step 3: Test get_air_quality**

Send: "Hoe is de luchtkwaliteit in Den Haag?"

- [ ] **Step 4: Test get_weather**

Send: "Wat is het weer in Groningen?"

- [ ] **Step 5: Document results**

---

### Task 37: Manual Test — Sales-adviseur (Riens + Sales Predictor)

- [ ] **Step 1: Select "Sales-adviseur" in the chatbot**

- [ ] **Step 2: Test get_gemeente_status (Riens)**

Send: "Wat is de contractstatus van gemeente Almere?"

- [ ] **Step 3: Test run_sales_forecast (Sales Predictor)**

Send: "Voorspel de sales voor de komende 6 maanden"

- [ ] **Step 4: Document results**

---

### Task 38: Error Path Testing

- [ ] **Step 1: Stop one MCP server and test graceful degradation**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
docker compose stop mcp-databank
```

Then in the chatbot, try to use a Databank tool. Expected: clear error message, not a crash.

- [ ] **Step 2: Restart the stopped server**

```bash
docker compose start mcp-databank
```

- [ ] **Step 3: Test with bad API key**

Temporarily change `DATABANK_AUTH_TOKEN` in the chatbot's .env to a wrong value, restart chatbot, and try a Databank tool.

Expected: auth rejection error, not a generic failure.

- [ ] **Step 4: Restore correct API key and restart**

---

### Task 39: Final Summary and Runbook

- [ ] **Step 1: Create the manual test runbook**

Write a file `product-docs/99-runbook/manual-test-runbook.md` with:

- Prerequisites (Docker, Ollama, Node.js, Python)
- Startup order (exact commands from this plan)
- Port allocation map
- Health check commands
- Manual test scenarios
- Teardown commands

- [ ] **Step 2: File all remaining issues**

- [ ] **Step 3: Commit all findings**

```bash
cd /home/ralph/Projects/Ruimtemeesters-Browser-Chatbot
git add product-docs/
git commit -m "docs: full-stack test round results — issues, runbook, findings"
```

- [ ] **Step 4: Print final summary**

List:

- Services that passed / failed
- Total issues found by severity
- Recommended next steps (fix critical/high issues, then re-test)
