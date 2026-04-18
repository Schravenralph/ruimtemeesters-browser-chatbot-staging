# Phase C4: OpenWebUI MCP Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect OpenWebUI to the 8 MCP servers via Docker Compose and native MCP Tool Server configuration, replace Phase A Python tools.

**Architecture:** Single shared Dockerfile builds all 8 MCP servers. Docker Compose runs them in HTTP mode on ports 3101-3108. OpenWebUI connects via `TOOL_SERVER_CONNECTIONS` env var. Assistants updated to reference MCP tool IDs. Phase A Python tools deleted.

**Tech Stack:** Docker, pnpm, Node.js 22, OpenWebUI v0.8.12 native MCP client

**Spec reference:** `docs/superpowers/specs/2026-04-02-phase-c4-openwebui-mcp-integration.md`

---

## File Structure

### MCP Servers repo (`/home/ralph/Projects/Ruimtemeesters-MCP-Servers/`)

| File                  | Responsibility                                 |
| --------------------- | ---------------------------------------------- |
| `Dockerfile`          | Shared multi-stage image for all 8 MCP servers |
| `docker-compose.yaml` | 8 services on ports 3101-3108, rm-network      |
| `.env.example`        | Add MCP port vars (already has API URLs/keys)  |

### OpenWebUI fork (`/home/ralph/Projects/ruimtemeesters-openwebui/`)

| File                              | Responsibility                               |
| --------------------------------- | -------------------------------------------- |
| `docker-compose.yaml`             | Add TOOL_SERVER_CONNECTIONS, join rm-network |
| `rm-tools/register_assistants.py` | Update toolIds to `server:mcp:*` format      |
| `rm-tools/databank.py`            | Delete                                       |
| `rm-tools/geoportaal.py`          | Delete                                       |
| `rm-tools/tsa.py`                 | Delete                                       |
| `rm-tools/dashboarding.py`        | Delete                                       |
| `rm-tools/riens.py`               | Delete                                       |
| `rm-tools/sales_predictor.py`     | Delete                                       |
| `rm-tools/opdrachten.py`          | Delete                                       |
| `rm-tools/aggregator.py`          | Delete                                       |
| `rm-tools/register_tools.py`      | Delete                                       |

---

## Task 1: Create Dockerfile for MCP servers

**Files:**

- Create: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
FROM node:22-slim

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
COPY packages/ packages/

RUN pnpm install --frozen-lockfile

ARG PACKAGE
ENV PACKAGE=${PACKAGE}
ENV MCP_TRANSPORT=http

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://localhost:' + (process.env.MCP_PORT || 3100) + '/health').then(r => r.ok ? process.exit(0) : process.exit(1)).catch(() => process.exit(1))"

CMD pnpm exec tsx packages/${PACKAGE}/src/server.ts --http --port ${MCP_PORT:-3100}
```

- [ ] **Step 2: Verify it builds for one server**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && docker build --build-arg PACKAGE=databank -t rm-mcp-databank .
```

Expected: successful build.

- [ ] **Step 3: Verify it starts**

```bash
docker run --rm -e MCP_PORT=3101 -p 3101:3101 rm-mcp-databank &
sleep 3
curl -s http://localhost:3101/health
docker stop $(docker ps -q --filter ancestor=rm-mcp-databank)
```

Expected: `{"status":"ok","transport":"http"}`

- [ ] **Step 4: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add Dockerfile
git commit -m "feat: add shared Dockerfile for all MCP servers"
```

---

## Task 2: Create docker-compose.yaml for MCP servers

**Files:**

- Create: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/docker-compose.yaml`
- Modify: `/home/ralph/Projects/Ruimtemeesters-MCP-Servers/.env.example`

- [ ] **Step 1: Create docker-compose.yaml**

```yaml
services:
  mcp-databank:
    build:
      context: .
      args:
        PACKAGE: databank
    container_name: rm-mcp-databank
    environment:
      - MCP_PORT=3101
      - DATABANK_API_URL=${DATABANK_API_URL:-http://host.docker.internal:4000}
      - DATABANK_AUTH_TOKEN=${DATABANK_AUTH_TOKEN:-}
    ports:
      - '3101:3101'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-geoportaal:
    build:
      context: .
      args:
        PACKAGE: geoportaal
    container_name: rm-mcp-geoportaal
    environment:
      - MCP_PORT=3102
      - GEOPORTAAL_API_URL=${GEOPORTAAL_API_URL:-http://host.docker.internal:5002/api}
      - GEOPORTAAL_API_KEY=${GEOPORTAAL_API_KEY:-}
    ports:
      - '3102:3102'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-tsa:
    build:
      context: .
      args:
        PACKAGE: tsa
    container_name: rm-mcp-tsa
    environment:
      - MCP_PORT=3103
      - TSA_API_URL=${TSA_API_URL:-http://host.docker.internal:8100}
      - TSA_API_KEY=${TSA_API_KEY:-}
    ports:
      - '3103:3103'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-dashboarding:
    build:
      context: .
      args:
        PACKAGE: dashboarding
    container_name: rm-mcp-dashboarding
    environment:
      - MCP_PORT=3104
      - DASHBOARDING_API_URL=${DASHBOARDING_API_URL:-http://host.docker.internal:5022}
      - DASHBOARDING_API_KEY=${DASHBOARDING_API_KEY:-}
    ports:
      - '3104:3104'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-riens:
    build:
      context: .
      args:
        PACKAGE: riens
    container_name: rm-mcp-riens
    environment:
      - MCP_PORT=3105
      - RIENS_API_URL=${RIENS_API_URL:-http://host.docker.internal:3001}
      - RIENS_API_KEY=${RIENS_API_KEY:-}
    ports:
      - '3105:3105'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-sales-predictor:
    build:
      context: .
      args:
        PACKAGE: sales-predictor
    container_name: rm-mcp-sales-predictor
    environment:
      - MCP_PORT=3106
      - SALES_PREDICTOR_API_URL=${SALES_PREDICTOR_API_URL:-http://host.docker.internal:8000}
      - SALES_PREDICTOR_API_KEY=${SALES_PREDICTOR_API_KEY:-}
    ports:
      - '3106:3106'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-opdrachten:
    build:
      context: .
      args:
        PACKAGE: opdrachten
    container_name: rm-mcp-opdrachten
    environment:
      - MCP_PORT=3107
      - OPDRACHTEN_API_URL=${OPDRACHTEN_API_URL:-http://host.docker.internal:6300}
      - OPDRACHTEN_API_KEY=${OPDRACHTEN_API_KEY:-}
    ports:
      - '3107:3107'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

  mcp-aggregator:
    build:
      context: .
      args:
        PACKAGE: aggregator
    container_name: rm-mcp-aggregator
    environment:
      - MCP_PORT=3108
      - AGGREGATOR_API_URL=${AGGREGATOR_API_URL:-http://host.docker.internal:6000}
      - AGGREGATOR_API_KEY=${AGGREGATOR_API_KEY:-}
    ports:
      - '3108:3108'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

networks:
  rm-network:
    name: rm-network
    driver: bridge
```

- [ ] **Step 2: Update .env.example with port vars**

Add MCP port section to the end of `.env.example`:

```env
# MCP Server Ports (used by docker-compose)
MCP_DATABANK_PORT=3101
MCP_GEOPORTAAL_PORT=3102
MCP_TSA_PORT=3103
MCP_DASHBOARDING_PORT=3104
MCP_RIENS_PORT=3105
MCP_SALES_PREDICTOR_PORT=3106
MCP_OPDRACHTEN_PORT=3107
MCP_AGGREGATOR_PORT=3108
```

- [ ] **Step 3: Build and start all services**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && docker compose build
```

Expected: all 8 images build successfully.

- [ ] **Step 4: Start and verify health**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers && docker compose up -d
sleep 5
for port in 3101 3102 3103 3104 3105 3106 3107 3108; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health || echo "FAILED"
done
docker compose down
```

Expected: all 8 return `{"status":"ok","transport":"http"}`.

- [ ] **Step 5: Commit**

```bash
cd /home/ralph/Projects/Ruimtemeesters-MCP-Servers
git add docker-compose.yaml .env.example
git commit -m "feat: add docker-compose with 8 MCP server services on rm-network"
```

---

## Task 3: Connect OpenWebUI to MCP servers

**Files:**

- Modify: `/home/ralph/Projects/ruimtemeesters-openwebui/docker-compose.yaml`

- [ ] **Step 1: Update OpenWebUI docker-compose.yaml**

Replace the full contents of `docker-compose.yaml` with:

```yaml
services:
  ollama:
    volumes:
      - ollama:/root/.ollama
    container_name: ollama
    pull_policy: always
    tty: true
    restart: unless-stopped
    image: ollama/ollama:${OLLAMA_DOCKER_TAG-latest}
    networks:
      - rm-network

  open-webui:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/open-webui/open-webui:${WEBUI_DOCKER_TAG-main}
    container_name: open-webui
    volumes:
      - open-webui:/app/backend/data
    depends_on:
      - ollama
    ports:
      - ${OPEN_WEBUI_PORT-3000}:8080
    environment:
      - 'OLLAMA_BASE_URL=http://ollama:11434'
      - 'WEBUI_SECRET_KEY='
      - 'TOOL_SERVER_CONNECTIONS=[{"type":"mcp","url":"http://rm-mcp-databank:3101/mcp","auth_type":"none","headers":{"X-API-Key":"${DATABANK_AUTH_TOKEN:-}"},"info":{"id":"rm-databank","name":"Ruimtemeesters Databank","description":"Policy documents, knowledge graph, beleidsscan"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-geoportaal:3102/mcp","auth_type":"none","headers":{"X-API-Key":"${GEOPORTAAL_API_KEY:-}"},"info":{"id":"rm-geoportaal","name":"Ruimtemeesters Geoportaal","description":"Spatial rules, air quality, weather, 3D buildings, PDOK"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-tsa:3103/mcp","auth_type":"none","headers":{"X-API-Key":"${TSA_API_KEY:-}"},"info":{"id":"rm-tsa","name":"Ruimtemeesters TSA","description":"Population forecasting with ML ensemble"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-dashboarding:3104/mcp","auth_type":"none","headers":{"X-API-Key":"${DASHBOARDING_API_KEY:-}"},"info":{"id":"rm-dashboarding","name":"Ruimtemeesters Dashboarding","description":"CBS/Primos demographic data and statistics"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-riens:3105/mcp","auth_type":"none","headers":{"X-API-Key":"${RIENS_API_KEY:-}"},"info":{"id":"rm-riens","name":"Ruimtemeesters Riens Sales Viewer","description":"Municipality contract status"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-sales-predictor:3106/mcp","auth_type":"none","headers":{"X-API-Key":"${SALES_PREDICTOR_API_KEY:-}"},"info":{"id":"rm-sales-predictor","name":"Ruimtemeesters Sales Predictor","description":"Sales forecasting with ML models"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-opdrachten:3107/mcp","auth_type":"none","headers":{"X-API-Key":"${OPDRACHTEN_API_KEY:-}"},"info":{"id":"rm-opdrachten","name":"Ruimtemeesters Opdrachten Scanner","description":"DAS/inhuur assignment pipeline"},"config":{"enable":true}},{"type":"mcp","url":"http://rm-mcp-aggregator:3108/mcp","auth_type":"none","headers":{"X-API-Key":"${AGGREGATOR_API_KEY:-}"},"info":{"id":"rm-aggregator","name":"Ruimtemeesters Aggregator","description":"Cross-app context, documents, spatial, knowledge graph"},"config":{"enable":true}}]'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-network

volumes:
  ollama: {}
  open-webui: {}

networks:
  rm-network:
    external: true
```

Key changes from original:

- Both services join `rm-network`
- `rm-network` declared as `external: true` (created by MCP compose or manually)
- `TOOL_SERVER_CONNECTIONS` env var with all 8 MCP server connections
- API key env vars reference host `.env` file

- [ ] **Step 2: Commit**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git add docker-compose.yaml
git commit -m "feat: connect OpenWebUI to 8 MCP servers via TOOL_SERVER_CONNECTIONS"
```

---

## Task 4: Update assistant tool assignments

**Files:**

- Modify: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/register_assistants.py`

- [ ] **Step 1: Update all toolIds in register_assistants.py**

Replace each `toolIds` array:

**Beleidsadviseur** (line 31):

```python
"toolIds": ["server:mcp:rm-databank", "server:mcp:rm-geoportaal", "server:mcp:rm-aggregator"],
```

**Demografie Analist** (line 59):

```python
"toolIds": ["server:mcp:rm-dashboarding", "server:mcp:rm-tsa"],
```

**Ruimtelijk Adviseur** (line 87):

```python
"toolIds": ["server:mcp:rm-geoportaal", "server:mcp:rm-databank", "server:mcp:rm-aggregator"],
```

**Sales Adviseur** (line 115):

```python
"toolIds": ["server:mcp:rm-riens", "server:mcp:rm-sales-predictor", "server:mcp:rm-opdrachten"],
```

**Ruimtemeesters Assistent** (line 145):

```python
"toolIds": ["server:mcp:rm-databank", "server:mcp:rm-geoportaal", "server:mcp:rm-tsa", "server:mcp:rm-dashboarding", "server:mcp:rm-riens", "server:mcp:rm-sales-predictor", "server:mcp:rm-opdrachten", "server:mcp:rm-aggregator"],
```

- [ ] **Step 2: Verify syntax**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui && python3 -c "
import ast
with open('rm-tools/register_assistants.py') as f:
    tree = ast.parse(f.read())
print('Syntax: OK')
# Verify all toolIds use new format
import re
with open('rm-tools/register_assistants.py') as f:
    content = f.read()
old = re.findall(r'\"rm_\w+\"', content)
new = re.findall(r'\"server:mcp:rm-\w+\"', content)
print(f'Old format refs: {len(old)} (should be 0)')
print(f'New format refs: {len(new)} (should be 20)')
"
```

Expected: `Syntax: OK`, `Old format refs: 0`, `New format refs: 20`.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git add rm-tools/register_assistants.py
git commit -m "feat: update assistant toolIds to MCP server format (server:mcp:rm-*)"
```

---

## Task 5: Delete Phase A Python tools

**Files:**

- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/databank.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/geoportaal.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/tsa.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/dashboarding.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/riens.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/sales_predictor.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/opdrachten.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/aggregator.py`
- Delete: `/home/ralph/Projects/ruimtemeesters-openwebui/rm-tools/register_tools.py`

- [ ] **Step 1: Delete all Phase A tool files and register_tools.py**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git rm rm-tools/databank.py rm-tools/geoportaal.py rm-tools/tsa.py rm-tools/dashboarding.py rm-tools/riens.py rm-tools/sales_predictor.py rm-tools/opdrachten.py rm-tools/aggregator.py rm-tools/register_tools.py
```

- [ ] **Step 2: Verify register_assistants.py still exists**

```bash
ls rm-tools/register_assistants.py
```

Expected: file exists.

- [ ] **Step 3: Commit**

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git commit -m "chore: remove Phase A Python tools — replaced by MCP servers"
```

---

## Task Dependencies

```
Task 1 (Dockerfile) ──→ Task 2 (docker-compose)
Task 3 (OpenWebUI config) — independent
Task 4 (assistant toolIds) — independent
Task 5 (delete rm-tools) — after Task 4
```

Tasks 1→2 are sequential (compose needs Dockerfile). Tasks 3 and 4 are independent of each other and of 1-2. Task 5 comes after Task 4 (update toolIds first, then delete old tools).

---

## Summary

After completing this plan:

- **Dockerfile** in MCP repo builds any server via `PACKAGE` build arg
- **docker-compose.yaml** runs 8 MCP servers on ports 3101-3108 on `rm-network`
- **OpenWebUI** connects to all 8 via `TOOL_SERVER_CONNECTIONS` with `X-API-Key` auth
- **5 assistants** reference MCP tool IDs (`server:mcp:rm-*`)
- **9 Phase A Python tool files** deleted from OpenWebUI fork
- **register_assistants.py** kept for re-seeding assistants with updated tool IDs
