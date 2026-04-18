#!/usr/bin/env bash
# Seed the OpenWebUI OpenAI-compatible connection list with a curated
# Gemini (Google AI Studio) endpoint.
#
# Idempotent — safe to re-run after DB reset, container rebuild, or
# `docker compose down -v`. Reads the Gemini key from the rm-chatbot
# container's OPENAI_API_KEYS env (position 1, 0-indexed).
#
# Usage:
#   scripts/seed-gemini-connection.sh
#
# Overrides:
#   HOST=http://localhost:3333
#   APP_CONTAINER=rm-chatbot
#   ADMIN_USER_ID=<uuid>     (defaults to first admin row in DB)

set -euo pipefail

HOST="${HOST:-http://localhost:3333}"
APP_CONTAINER="${APP_CONTAINER:-rm-chatbot}"
DB_CONTAINER="${DB_CONTAINER:-rm-chatbot-db}"

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

# Extract Gemini key from the container's env (position 1 in OPENAI_API_KEYS=A;B).
GEMINI_KEY=$(docker exec "$APP_CONTAINER" sh -c 'printf "%s" "$OPENAI_API_KEYS"' | cut -d';' -f2)
if [ -z "$GEMINI_KEY" ]; then
  echo "GEMINI_API_KEY missing from container env. Set GEMINI_API_KEY in .env and recreate the container." >&2
  exit 1
fi

# Mint a short-lived admin JWT inside the container (uses its own WEBUI_SECRET_KEY).
# Pass ADMIN_USER_ID via env (-e) and read it from os.environ inside Python —
# nothing gets interpolated into the source so a UUID with unusual chars can't
# break out of the Python string literal (defensive — UUIDs shouldn't contain
# quotes, but external inputs don't belong in source either).
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

# Build the request body with python's json.dumps so GEMINI_KEY and every other
# value are JSON-escaped correctly. Keys that ever contain "/\ or control chars
# (Google AI Studio keys don't today, but this is the right shape for any
# secret) don't corrupt the payload.
BODY=$(GEMINI_KEY="$GEMINI_KEY" python3 - <<'PY'
import json, os
body = {
  "ENABLE_OPENAI_API": True,
  "OPENAI_API_BASE_URLS": [
    "https://api.openai.com/v1",
    "https://generativelanguage.googleapis.com/v1beta/openai",
  ],
  "OPENAI_API_KEYS": ["", os.environ["GEMINI_KEY"]],
  "OPENAI_API_CONFIGS": {
    "0": {"enable": False, "connection_type": "external"},
    "1": {
      "enable": True,
      "connection_type": "external",
      "prefix_id": "gemini",
      "tags": [{"name": "Google"}],
      "model_ids": [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
      ],
    },
  },
}
print(json.dumps(body))
PY
)

RESP=$(curl -sS -X POST "$HOST/openai/config/update" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BODY")

# Sanity-check the response
echo "$RESP" | python3 -c "
import json, sys
r = json.load(sys.stdin)
cfgs = r.get('OPENAI_API_CONFIGS', {})
gemini_models = cfgs.get('1', {}).get('model_ids', [])
if len(gemini_models) != 5:
    print(f'ERROR: expected 5 Gemini models, got {len(gemini_models)}', file=sys.stderr)
    sys.exit(2)
print('seeded: ' + ', '.join(gemini_models))
"
