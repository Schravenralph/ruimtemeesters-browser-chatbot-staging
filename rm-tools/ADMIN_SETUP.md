# OpenWebUI Admin Setup — External Tool Servers (MCP)

One-time setup per environment (staging, prod). The registrar script
(`register_assistants.py`) only creates assistant models + slash prompts —
the MCP tool servers themselves must be registered by an admin in the
OpenWebUI UI.

## Prerequisites

- Admin login to OpenWebUI
- Ruimtemeesters-MCP-Servers deployed + all containers healthy
- Clerk OAuth configured on the gateway (`mcp.datameesters.nl`)
- A per-user Clerk-issued bearer token (obtained via the OpenWebUI OAuth
  flow against the gateway), OR a service-account token if running a
  shared assistant

## Steps

1. Sign in to OpenWebUI as admin.
2. **Admin Settings → External Tools → + Add Server** for each row below.
3. For each: **Type = MCP (Streamable HTTP)**, **Auth = Bearer**, **Key = \<your token\>**.

| Server ID in OpenWebUI | URL                                          | Used by assistants                                             |
| ---------------------- | -------------------------------------------- | -------------------------------------------------------------- |
| `rm-memory`            | `https://mcp.datameesters.nl/memory/mcp`     | Ruimtemeesters Assistent                                       |
| `rm-databank`          | `https://mcp.datameesters.nl/databank/mcp`   | Beleidsadviseur, Ruimtelijk Adviseur, Ruimtemeesters Assistent |
| `rm-geoportaal`        | `https://mcp.datameesters.nl/geoportaal/mcp` | Ruimtelijk Adviseur, Ruimtemeesters Assistent                  |

<!-- Note: the 5 specialist assistants are pre-existing; the policy going forward is ONE general agent (`rm-assistent`) with skill files + slash prompts, not per-role specialists. See ADR-024 in Databank. Specialists will be consolidated in a follow-up PR. -->

| `rm-tsa` | `https://mcp.datameesters.nl/tsa/mcp` | Demografie Analist, Ruimtemeesters Assistent |
| `rm-dashboarding` | `https://mcp.datameesters.nl/dashboarding/mcp` | Demografie Analist, Ruimtemeesters Assistent |
| `rm-riens` | `https://mcp.datameesters.nl/riens/mcp` | Sales Adviseur, Ruimtemeesters Assistent |
| `rm-sales-predictor` | `https://mcp.datameesters.nl/sales-predictor/mcp` | Sales Adviseur, Ruimtemeesters Assistent |
| `rm-opdrachten` | `https://mcp.datameesters.nl/opdrachten/mcp` | Sales Adviseur, Ruimtemeesters Assistent |
| `rm-aggregator` | `https://mcp.datameesters.nl/aggregator/mcp` | Beleidsadviseur, Ruimtelijk Adviseur, Ruimtemeesters Assistent |
| `rm-knowledge` _(planned)_ | `https://mcp.datameesters.nl/knowledge/mcp` | Ruimtemeesters Assistent |

The `rm-knowledge` row is **not live yet** — see `Ruimtemeesters-MCP-Servers/docs/superpowers/specs/2026-04-17-memory-knowledge-tools.md`. It will host the Claude-Code-style `save_memory` / `recall_memory` / `get_memory` / `list_memories` / `forget_memory` tools. Architectural question (same `@rm-mcp/memory` package vs separate `@rm-mcp/knowledge`) is still open.

**Exact server-ID string matters.** The IDs above match what
`register_assistants.py` puts in each assistant's `meta.toolIds` (as
`server:mcp:<id>`). A mismatch breaks the tool wiring silently — the UI
will show the assistant but no tools will be available.

## Sanity check

After adding each server: the UI's **Test connection** button (or the
first tool call from an assistant using that server) should succeed.

For `rm-memory` specifically:

```
curl -s -X POST https://mcp.datameesters.nl/memory/mcp \
  -H "Authorization: Bearer $YOUR_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expect a JSON-RPC response listing 4 tools:
`create_bopa_session`, `get_bopa_session`, `list_bopa_sessions`,
`update_bopa_session`.

## Running the registrar

Once all tool servers are registered in the UI, run:

```
python rm-tools/register_assistants.py \
  --url https://chat.datameesters.nl \
  --token <your admin JWT>
```

Output ends with `Models: 5/5` and `Prompts: 11/11` when successful.

To preview without touching the server:

```
python rm-tools/register_assistants.py --dry-run
```

## Ordering

1. Deploy `Ruimtemeesters-MCP-Servers` (new `memory` profile + gateway
   route for it)
2. Verify the gateway's `/services` endpoint lists `memory`
3. Register the 9 tool servers in the OpenWebUI UI per the table above
4. Run the registrar
5. Smoke-test: pick **BOPA Adviseur** in the UI, use suggestion-prompt #1
6. Check `memory.bopa_sessions` row created with
   `api_key_name LIKE 'gateway:%'`

Steps 1–2 happen once per environment. Steps 3–4 are re-runnable any
time the MCP surface changes.
