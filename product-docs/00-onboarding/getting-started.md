# Getting Started

## Prerequisites

- Docker + Docker Compose
- Access to the Hetzner server (157.180.106.205)
- Clerk account (ralphdrmoller@gmail.com) for datameesters.nl

## Repositories

| Repo             | Location                                              | Purpose                               |
| ---------------- | ----------------------------------------------------- | ------------------------------------- |
| **Product repo** | `/home/ralph/Projects/Ruimtemeesters-Browser-Chatbot` | Docs, specs, plans                    |
| **Staging fork** | `/home/ralph/Projects/ruimtemeesters-openwebui`       | OpenWebUI fork with RM customizations |

The staging fork is a fork of [open-webui/open-webui](https://github.com/open-webui/open-webui) at [Schravenralph/ruimtemeesters-browser-chatbot-staging](https://github.com/Schravenralph/ruimtemeesters-browser-chatbot-staging).

## Running Locally

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui

# Copy env template
cp .env.rm.example .env
# Edit .env — fill in WEBUI_SECRET_KEY, Clerk credentials, API keys

# Create shared Docker network (first time only)
docker network create rm-network

# Start the stack
docker compose -f docker-compose.rm.yaml up -d --build

# Pull Ollama models (first time only)
docker exec rm-ollama ollama pull llama3.1
docker exec rm-ollama ollama pull mistral
```

The chatbot is at http://localhost:3333.

## Registering Tools and Assistants

After the stack is running, register the RM tools and assistants:

```bash
# Get an admin JWT from the browser: localStorage.token
TOKEN="<paste-token>"

# Register 8 tools
python3 rm-tools/register_tools.py --url http://localhost:3333 --token "$TOKEN"

# Register 5 assistants + 8 prompt templates
python3 rm-tools/register_assistants.py --url http://localhost:3333 --token "$TOKEN"
```

## Production

- **chatbot.datameesters.nl** — primary chatbot URL
- **rob.datameesters.nl** — alias
- **Caddy** reverse proxy at `/etc/caddy/Caddyfile`
- **SSO** via Clerk OIDC from datameesters.nl

## Upstream Syncing

```bash
cd /home/ralph/Projects/ruimtemeesters-openwebui
git fetch upstream
git checkout -b upstream-sync
git merge upstream/main
# Resolve conflicts, test, merge to main
```
