# System Design

## Architecture Overview

```
Users (Browser)
       │
  Clerk SSO (.datameesters.nl)
       │
  OpenWebUI Fork (chatbot.datameesters.nl / rob.datameesters.nl)
  ├── SvelteKit frontend (branded)
  ├── Python/FastAPI backend
  ├── LLM providers: Ollama (local), OpenAI, Claude
  ├── PostgreSQL (conversations, users, audit)
  └── Tool layer (8 tools calling app APIs)
       │
  ┌────┴────────────────────────────────────────┐
  │  Direct app calls (default)                  │
  │  Aggregator (cross-app composition only)     │
  └──────────────────────────────────────────────┘
       │
  ┌────┴──────┬──────────┬─────────┬─────────┬──────────┬──────────┬────────────┐
  Databank  Geoportaal  Dashb.    TSA      Riens    Sales-P   Opdrachten  Aggregator
  (beleid)  (spatial)   (CBS)   (forecast) (sales)  (ML)      (pipeline)  (cross-app)
```

## Integration Model

**Default:** Chatbot calls app APIs directly via OpenWebUI Tools.

**Aggregator:** Only for cross-app composition — queries that span Databank + Geoportaal.

**No duplication:** If an app has an endpoint, we don't recreate it in the Aggregator.

## Auth Flow

```
Clerk login at datameesters.nl
  → OIDC auto-redirect at chatbot.datameesters.nl
  → Clerk recognizes session → callback → OpenWebUI session created
```

Three layers:
1. **Clerk** — identity (who you are)
2. **OpenWebUI** — chatbot permissions (what models/tools you see)
3. **Apps** — data-level RBAC (what data you can access)

## Stack

| Component | Technology |
|-----------|-----------|
| Chat UI | SvelteKit (OpenWebUI fork) |
| Backend | Python (FastAPI) |
| Database | PostgreSQL |
| Local LLM | Ollama (llama3.1, mistral) |
| Remote LLMs | OpenAI, Anthropic Claude |
| Auth | Clerk OIDC |
| Reverse proxy | Caddy |
| Tools | 8 OpenWebUI Tools (Python → httpx → app APIs) |
| Assistants | 5 Modelfiles with curated tool access |
