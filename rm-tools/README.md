# Ruimtemeesters AI — Assistant Registration

Scripts for managing Ruimtemeesters assistants in OpenWebUI.

Tools are now provided by MCP servers (see `Ruimtemeesters-MCP-Servers` repo).

## Register Assistants

```bash
python rm-tools/register_assistants.py --url http://localhost:3333 --token <admin-token>
```

The admin JWT can be obtained from the browser after logging in:

- DevTools → Console → `localStorage.token`
- Or from the `token` cookie
