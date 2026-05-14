#!/usr/bin/env bash
# Seed the OpenWebUI OpenAI-compatible connection list with the single
# LiteLLM-proxy connection (post-cutover, ADR-0010).
#
# Idempotent — safe to re-run after DB reset, container rebuild, or
# `docker compose down -v`. Reads LITELLM_MASTER_KEY from the rm-chatbot
# container's OPENAI_API_KEYS env (post-cutover that env holds a single
# value: the LiteLLM master key).
#
# Why this script still exists when the env should be enough:
# OpenWebUI's `OPENAI_API_BASE_URLS` / `OPENAI_API_KEYS` / `OPENAI_API_CONFIGS`
# are all PersistentConfig — read from env on FIRST boot, then DB wins.
# An existing prod with stale 3-provider state from the pre-cutover
# seed-gemini-connection.sh keeps showing direct OpenAI / Gemini /
# OpenRouter connections after a redeploy. This script POSTs the new
# single-LiteLLM shape to /openai/config/update to overwrite that state.
#
# Also resets DEFAULT_MODELS to the bare LiteLLM model_name (no prefix_id
# survives the cutover) — pre-cutover users had `gemini.gemini-2.5-flash-lite`
# in their per-instance config which no longer resolves. Done by reading
# the full config via /api/v1/configs/export, mutating ui.default_models,
# and writing the merged blob back via /api/v1/configs/import (the import
# handler is a full overwrite, so a partial-key POST would wipe everything
# else).
#
# Usage:
#   scripts/seed-litellm-connection.sh
#
# After seeding, verify the resulting DB state with:
#   scripts/verify-llm-connections.sh
#
# Overrides:
#   HOST=http://localhost:3333
#   APP_CONTAINER=rm-chatbot
#   DB_CONTAINER=rm-chatbot-db
#   ADMIN_USER_ID=<uuid>             (defaults to first admin row in DB)
#   DEFAULT_MODEL=RO-Assistent        (must match a model_name in litellm/config.yaml)

set -euo pipefail

HOST="${HOST:-http://localhost:3333}"
APP_CONTAINER="${APP_CONTAINER:-rm-chatbot}"
DB_CONTAINER="${DB_CONTAINER:-rm-chatbot-db}"
DEFAULT_MODEL="${DEFAULT_MODEL:-RO-Assistent}"

# Persona Model rows we no longer want around. Cleared at the start of the
# persona-seeding phase below so they don't linger in the dropdown after
# a rename. Add to this list whenever a persona id is retired.
LEGACY_PERSONA_IDS="RO-Bot JURA Schets Meester"

# Resolve admin user id from DB if not provided.
ADMIN_USER_ID="${ADMIN_USER_ID:-}"
if [ -z "$ADMIN_USER_ID" ]; then
  ADMIN_USER_ID=$(docker exec "$DB_CONTAINER" psql -U rmchatbot -d rmchatbot -tAc \
    "SELECT id FROM \"user\" WHERE role = 'admin' ORDER BY created_at LIMIT 1;" 2>/dev/null | tr -d '[:space:]')
  if [ -z "$ADMIN_USER_ID" ]; then
    echo "No admin user found in DB. Sign in at $HOST first, or pass ADMIN_USER_ID." >&2
    exit 1
  fi
fi

# Extract the single LiteLLM key from the container's env. Post-cutover
# OPENAI_API_KEYS holds one value (LITELLM_MASTER_KEY) — same shape, simpler
# parsing than the old 3-provider semicolon-list.
LITELLM_KEY=$(docker exec "$APP_CONTAINER" sh -c 'printf "%s" "$OPENAI_API_KEYS"')
if [ -z "$LITELLM_KEY" ]; then
  echo "OPENAI_API_KEYS missing from container env (expected LITELLM_MASTER_KEY post-cutover)." >&2
  echo "Set LITELLM_MASTER_KEY in .env and recreate the container." >&2
  exit 1
fi

# Mint a short-lived admin JWT inside the container (uses its own WEBUI_SECRET_KEY).
TOKEN=$(docker exec -i -e ADMIN_USER_ID="$ADMIN_USER_ID" "$APP_CONTAINER" python3 - <<'PY' 2>/dev/null | tail -1
import os
from datetime import timedelta
from open_webui.utils.auth import create_token
print(create_token({'id': os.environ['ADMIN_USER_ID']}, timedelta(minutes=5)))
PY
)
if [ -z "$TOKEN" ]; then
  echo "Failed to mint admin token in container $APP_CONTAINER." >&2
  exit 1
fi

# --- 1. Connection ----------------------------------------------------------
# Single LiteLLM connection. Bare model_name strings — these MUST match the
# `model_name` keys in litellm/config.yaml exactly (LiteLLM uses them as the
# routing keys to dispatch to the underlying provider). No `prefix_id` so the
# dropdown shows clean names like `gemini-2.5-flash-lite` rather than
# `litellm.gemini-2.5-flash-lite`.
BODY=$(LITELLM_KEY="$LITELLM_KEY" python3 - <<'PY'
import json, os

litellm_key = os.environ['LITELLM_KEY']

base_urls = ['http://litellm:4000/v1']
keys = [litellm_key]
configs = {
    '0': {
        'enable': True,
        'connection_type': 'external',
        'tags': [{'name': 'Ruimtemeesters AI'}],
        # Three RM personas. IDs must match `model_name` keys in
        # litellm/config.yaml (LiteLLM uses these as routing keys).
        # The display name + system prompt come from the OWUI Model rows
        # seeded later in this script.
        'model_ids': ['RO-Assistent', 'Juridisch-Assistent', 'Commercieel-Assistent'],
    },
}

print(json.dumps({
    'ENABLE_OPENAI_API': True,
    'OPENAI_API_BASE_URLS': base_urls,
    'OPENAI_API_KEYS': keys,
    'OPENAI_API_CONFIGS': configs,
}))
PY
)

# `--fail-with-body` (curl >= 7.76) makes curl exit non-zero on HTTP 4xx/5xx
# while still printing the response body to stdout — combined with `set -e`
# at the top, this aborts the script before any subsequent step (read,
# mutate, re-import) can act on a broken response. Without this, a 401 from
# an expired token would parse as valid JSON and the next /configs/import
# call would full-overwrite the saved config with garbage.
RESP=$(curl -sS --fail-with-body -X POST "$HOST/openai/config/update" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BODY")

echo "$RESP" | python3 -c "
import json, sys
r = json.load(sys.stdin)
urls = r.get('OPENAI_API_BASE_URLS', [])
cfgs = r.get('OPENAI_API_CONFIGS', {})
models = cfgs.get('0', {}).get('model_ids', [])

if urls != ['http://litellm:4000/v1']:
    print(f'ERROR: expected single litellm URL, got {urls}', file=sys.stderr)
    sys.exit(2)
if len(models) != 3:
    print(f'ERROR: expected 3 personas, got {len(models)}', file=sys.stderr)
    sys.exit(2)

print('seeded litellm connection: ' + ', '.join(models))
"

# --- 2. DEFAULT_MODELS ------------------------------------------------------
# /api/v1/configs/import does a full save_config(form_data.config) overwrite,
# so we read-modify-write the whole blob to avoid clobbering everything else
# (banners, branding, MCP tool servers — all in this same JSON document).
#
# `--fail-with-body` is critical here: a 401/403 on /configs/export would
# otherwise parse as valid JSON `{"detail": "..."}`, get `ui.default_models`
# merged into it, and then /configs/import would replace the real config
# with that two-key blob. Bugbot caught this on f0d07a8.
EXPORT=$(curl -sS --fail-with-body "$HOST/api/v1/configs/export" \
  -H "Authorization: Bearer $TOKEN")

MERGED=$(EXPORT="$EXPORT" DEFAULT_MODEL="$DEFAULT_MODEL" python3 - <<'PY'
import json, os, sys
cfg = json.loads(os.environ['EXPORT'])
# Defense in depth: even after --fail-with-body, refuse to mutate a response
# that doesn't look like an OWUI config. /configs/export should always
# return a dict with `openai` (set up earlier in this script) and `ui`
# (default_models lives here). If neither is present, something's wrong.
if not isinstance(cfg, dict) or ('openai' not in cfg and 'ui' not in cfg):
    print(f'ERROR: /configs/export returned an unexpected shape (top-level keys: {list(cfg)[:10] if isinstance(cfg, dict) else type(cfg).__name__}); refusing to import.', file=sys.stderr)
    sys.exit(2)
cfg.setdefault('ui', {})['default_models'] = os.environ['DEFAULT_MODEL']
# Lock the model surface to the codenamed LiteLLM connection only.
# Without these, an existing DB has `ollama.enable=true` (auto-discovers
# any local Ollama models like qwen) and `evaluation.arena.enable=true`
# (admin A/B-comparison models), both of which would surface in the user
# picker alongside RO/Juridisch/Commercieel Assistent.
cfg.setdefault('ollama', {})['enable'] = False
cfg.setdefault('evaluation', {}).setdefault('arena', {})['enable'] = False
print(json.dumps({'config': cfg}))
PY
)

IMPORT_RESP=$(curl -sS --fail-with-body -X POST "$HOST/api/v1/configs/import" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$MERGED")

echo "$IMPORT_RESP" | DEFAULT_MODEL="$DEFAULT_MODEL" python3 -c "
import json, os, sys
r = json.load(sys.stdin)
got = r.get('ui', {}).get('default_models')
want = os.environ['DEFAULT_MODEL']
ollama_enabled = r.get('ollama', {}).get('enable')
arena_enabled = r.get('evaluation', {}).get('arena', {}).get('enable')
ok = True
if got != want:
    print(f'ERROR: default_models is {got!r}, expected {want!r}', file=sys.stderr); ok = False
if ollama_enabled is not False:
    print(f'ERROR: ollama.enable is {ollama_enabled!r}, expected False', file=sys.stderr); ok = False
if arena_enabled is not False:
    print(f'ERROR: evaluation.arena.enable is {arena_enabled!r}, expected False', file=sys.stderr); ok = False
if not ok:
    sys.exit(2)
print(f'reset default_models = {got}')
print('disabled ollama.enable, evaluation.arena.enable')
"

# --- 3. Persona Model rows (system prompts) ---------------------------------
# OWUI Model rows are the overlay that gives a base LiteLLM alias a display
# name + system prompt + description. Without them, "RO-Bot" and "JURA" would
# show in the picker but reach the model with no system prompt — Opus default
# voice, no RM domain framing.
#
# Idempotent: /api/v1/models/create returns 401 if the id already exists, so
# we delete-then-create on each run. The delete is best-effort (no failure if
# the row didn't exist yet).
seed_persona() {
  local id="$1"
  local display_name="$2"
  local description="$3"
  local system_prompt="$4"
  # 5th arg: comma-separated list of MCP tool ids (without the
  # `server:mcp:` prefix) — e.g. "rm-databank,rm-geoportaal,rm-memory".
  # Empty / missing = no curation (model gets default tool surface).
  local tool_ids_csv="${5:-}"

  # Best-effort delete first so re-runs apply prompt edits cleanly.
  # Body shape is `{"id": "..."}` per ModelIdForm in routers/models.py;
  # the earlier query-string variant returned 401 silently.
  curl -sS -X POST "$HOST/api/v1/models/model/delete" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"$id\"}" >/dev/null 2>&1 || true

  local body
  body=$(ID="$id" NAME="$display_name" DESC="$description" SYS="$system_prompt" TOOLS="$tool_ids_csv" python3 - <<'PY'
import json, os
# `base_model_id: None` is critical: it puts this Model row in OWUI's
# *override* branch (utils/models.py:150 — "Override applied directly to
# a base model (shares the same ID)"), which mutates the LiteLLM-discovered
# base model's `name` field to the long display string. Setting
# base_model_id to the same id sends the row down the *new model* branch
# instead, where utils/models.py:177 short-circuits with `continue`
# because the id already exists in the LiteLLM-discovered list — so the
# row exists in DB but its long name never reaches the dropdown.
# System prompt still reaches the chat path either way (read directly
# from the Model row at request time).
meta = {
    'description': os.environ['DESC'],
    # Profile image fallback already serves the Ralph mascot for any
    # model without a custom URL — no need to set one here.
    #
    # Auto-enable Brave web search for every chat with this persona.
    # `capabilities.web_search` whitelists the feature for the model
    # (Chat.svelte:350 gate), and `defaultFeatureIds=['web_search']`
    # toggles the globe ON when the user enters the chat
    # (Chat.svelte:354). User can still turn it off per-message.
    'capabilities': {'web_search': True},
    'defaultFeatureIds': ['web_search'],
}
# Per-persona tool curation. `meta.toolIds` is the list of tools that
# get pre-selected when the user opens a chat with this model. They can
# still toggle additional ones via the picker, but the persona's defaults
# steer the model toward its domain (RO -> Geoportaal/Databank,
# Juridisch -> Databank only, Commercieel -> Riens/Opdrachten/Sales).
# MCP tool ids in OWUI use the `server:mcp:<id>` prefix — see
# backend/open_webui/utils/middleware.py:2475.
tools_csv = os.environ.get('TOOLS', '').strip()
if tools_csv:
    meta['toolIds'] = [f'server:mcp:{t.strip()}' for t in tools_csv.split(',') if t.strip()]

print(json.dumps({
    'id': os.environ['ID'],
    'base_model_id': None,
    'name': os.environ['NAME'],
    'meta': meta,
    'params': {
        # OpenWebUI reads params.system at chat time and prepends it as a
        # system message before the user's history.
        'system': os.environ['SYS'],
    },
    'is_active': True,
}))
PY
)

  curl -sS --fail-with-body -X POST "$HOST/api/v1/models/create" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | python3 -c "
import json, sys
r = json.load(sys.stdin)
if r is None or 'id' not in r:
    print(f'ERROR: model create returned {r!r}', file=sys.stderr); sys.exit(2)
print(f\"  seeded persona: {r.get('id')} -> {r.get('name')}\")
"
}

echo "Cleaning up legacy persona Model rows..."
for legacy_id in $LEGACY_PERSONA_IDS; do
  resp=$(curl -sS -X POST "$HOST/api/v1/models/model/delete" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"$legacy_id\"}" 2>&1 || true)
  # `True` = a row was deleted, anything else (incl. 401 NOT_FOUND) means
  # the legacy id wasn't around — silent skip rather than spam.
  case "$resp" in
    true) echo "  deleted legacy persona: $legacy_id" ;;
  esac
done

echo "Seeding persona Model rows..."

seed_persona "RO-Assistent" "RO Assistent" \
  "Sparringpartner voor adviseurs bij Ruimtemeesters." \
  "Je bent de RO Assistent voor adviseurs bij Ruimtemeesters. Nederlands.

Regels:
- Bij twijfel: tool gebruiken, terugvragen, of zeggen dat je het niet zeker weet. Niet gokken, niet aannemen, niet verzinnen.
- <map-context> resolveert alleen deictische verwijzingen ('hier', 'dit', 'deze locatie'). 'Waar zit Ruimtemeesters?' is GEEN deictische vraag — gebruik een tool of erken dat je het niet weet. Voeg ook geen losse claims over die selectie toe ('dit is het kantoor van X') tenzij een tool dat bevestigt.
- Geen rauwe coördinaten. Wikkel adressen als [[place:<volledig adres>]], features als [[feature:<layerKey>/<featureId>]], klikbare acties als [[action:pan_map:{\"lon\":<n>,\"lat\":<n>,\"zoom\":<n>}]] (alleen na een geocodeer-tool)." \
  "rm-databank,rm-geoportaal,rm-tsa,rm-dashboarding,rm-aggregator,rm-memory"

seed_persona "Juridisch-Assistent" "Juridisch Assistent" \
  "Juridische sparringpartner voor adviseurs — Omgevingswet, Awb, Wro en jurisprudentie." \
  "Je bent de Juridisch Assistent voor adviseurs bij Ruimtemeesters. Nederlands.

Regels:
- Bij twijfel: bron citeren met vindplaats, of zeggen dat je het niet zeker weet. Niet gokken, niet aannemen, niet verzinnen.
- Onderscheid vaste lijn en open norm; benoem bandbreedte in interpretatie.
- Geen advies geven dat een gemachtigd jurist zou moeten geven — signaleer wanneer een vraag dat raakt." \
  "rm-databank,rm-aggregator,rm-memory"

seed_persona "Commercieel-Assistent" "Commercieel Assistent" \
  "Commerciële sparringpartner — tendering, aanbestedingen, opdrachten, sales pipeline en opportunities per gemeente." \
  "Je bent de Commercieel Assistent voor adviseurs bij Ruimtemeesters. Nederlands.

Regels:
- Bij twijfel: tool of bron raadplegen, of zeggen dat je het niet zeker weet. Niet gokken, niet aannemen, niet verzinnen.
- Geen go/no-go-beslissing op tenders — schets afwegingen en beveel menselijke beoordeling aan." \
  "rm-opdrachten,rm-riens,rm-sales-predictor,rm-dashboarding,rm-aggregator,rm-memory"

echo "Done."
