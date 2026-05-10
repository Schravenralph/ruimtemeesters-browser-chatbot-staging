#!/usr/bin/env bash
# Verify the OpenWebUI OpenAI-compatible connection list matches the
# single-LiteLLM shape that seed-litellm-connection.sh writes (post-cutover,
# ADR-0010).
#
# Emits JSON to stdout (parallel to scripts/measure-brand.sh).
# Exit 0 when every criterion passes, 1 otherwise.
#
# Usage:
#   scripts/verify-llm-connections.sh
#   scripts/verify-llm-connections.sh | jq .
#
# Overrides:
#   HOST=http://localhost:3333
#   APP_CONTAINER=rm-chatbot
#   DB_CONTAINER=rm-chatbot-db
#   ADMIN_USER_ID=<uuid>             (defaults to first admin row in DB)
#   EXPECT_LITELLM_URL=http://litellm:4000/v1
#   EXPECT_MODEL_COUNT=3     (RO + Juridisch + Commercieel Assistent)

set -uo pipefail

HOST="${HOST:-http://localhost:3333}"
APP_CONTAINER="${APP_CONTAINER:-rm-chatbot}"
DB_CONTAINER="${DB_CONTAINER:-rm-chatbot-db}"
EXPECT_LITELLM_URL="${EXPECT_LITELLM_URL:-http://litellm:4000/v1}"
EXPECT_MODEL_COUNT="${EXPECT_MODEL_COUNT:-3}"

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

CONFIG=$(curl -sS "$HOST/openai/config" -H "Authorization: Bearer $TOKEN")

# Validate and emit JSON. Exit non-zero on any criterion failure.
HOST="$HOST" CONFIG="$CONFIG" \
  EXPECT_LITELLM_URL="$EXPECT_LITELLM_URL" \
  EXPECT_MODEL_COUNT="$EXPECT_MODEL_COUNT" \
  python3 <<'PYEOF'
import json, os, sys, datetime

raw = os.environ.get("CONFIG", "{}")
try:
    cfg = json.loads(raw)
except Exception as e:
    print(f"verify-llm-connections: failed to parse /openai/config response: {e}", file=sys.stderr)
    print(raw[:400], file=sys.stderr)
    sys.exit(1)

expect_url = os.environ["EXPECT_LITELLM_URL"]
expect_count = int(os.environ["EXPECT_MODEL_COUNT"])

base_urls = cfg.get("OPENAI_API_BASE_URLS", []) or []
configs = cfg.get("OPENAI_API_CONFIGS", {}) or {}
enabled = cfg.get("ENABLE_OPENAI_API")

# A — OpenAI-compat layer is enabled
a_pass = enabled is True

# B — exactly one connection (post-cutover shape)
b_pass = len(base_urls) == 1

# C — the one connection points at LiteLLM
c_url = base_urls[0] if base_urls else ""
c_pass = c_url == expect_url

# D — the LiteLLM connection has the expected curated model list and is enabled
d = configs.get("0", {}) or {}
d_models = d.get("model_ids", []) or []
d_enabled = bool(d.get("enable"))
d_prefix = d.get("prefix_id", "")
d_pass = d_enabled and len(d_models) == expect_count and d_prefix == ""

criteria = {
    "A_openai_api_enabled": {"value": enabled, "pass": a_pass},
    "B_single_connection": {
        "value": len(base_urls),
        "expected": 1,
        "pass": b_pass,
    },
    "C_url_is_litellm": {
        "value": c_url,
        "expected": expect_url,
        "pass": c_pass,
    },
    "D_litellm_connection": {
        "enabled": d_enabled,
        "prefix_id": d_prefix,
        "model_count": len(d_models),
        "expected_count": expect_count,
        "model_ids": d_models,
        "pass": d_pass,
    },
}

all_pass = all(v.get("pass", False) for v in criteria.values())

out = {
    "timestamp": datetime.datetime.now().astimezone().isoformat(),
    "host": os.environ.get("HOST"),
    "criteria": criteria,
    "all_pass": all_pass,
}
print(json.dumps(out, indent=2))

if not all_pass:
    failed = [k for k, v in criteria.items() if not v.get("pass", False)]
    print(f"verify-llm-connections: failed criteria: {', '.join(failed)}", file=sys.stderr)
    sys.exit(1)
PYEOF
