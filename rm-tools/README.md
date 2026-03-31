# Ruimtemeesters AI — OpenWebUI Tools

Custom tools for the Ruimtemeesters chatbot. Each file is a standalone
OpenWebUI Tool that gets registered via the API.

## Registration

```bash
python rm-tools/register_tools.py --url http://localhost:3333 --token <admin-token>
```

The admin JWT can be obtained from the browser after logging in:
- DevTools → Console → `localStorage.token`
- Or from the `token` cookie

## Tool Files

| File | App | Capabilities |
|------|-----|-------------|
| databank.py | Databank | Search beleid, knowledge graph, queries |
| geoportaal.py | Geoportaal | Spatial rules, air quality, weather, buildings |
| dashboarding.py | Dashboarding | Data, stats, trends |
| tsa.py | TSA Engine | Forecasts, backtests, diagnostics |
| riens.py | Riens Sales Viewer | Municipality status |
| sales_predictor.py | Sales Predictor | Train, predict, compare |
| opdrachten.py | Opdrachten Scanner | Inbox, pipeline, library |

## Valves

Each tool has configurable Valves (admin settings) for the app URL and timeout.
Configure these in OpenWebUI → Workspace → Tools → [Tool] → Valves.
