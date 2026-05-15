#!/usr/bin/env bash
# End-to-end smoke for the advisor's thematic policy scan flow.
#
# Verifies the critical-path stack after these PRs deploy together:
#   - feat/skills-mcp-package        (MCP-Servers PR #101)
#   - feat/active-project-tool       (Memory       PR #30)
#   - feat/skills-context-filter     (Browser-Chatbot PR #110)
#
# Spec: product-docs/superpowers/specs/2026-05-15-e2e-thematic-scan-smoke.md
# Tracking: Browser-Chatbot #108, MCP-Servers #98, Memory #28, Skills #11
#
# Usage:
#   scripts/smoke/thematic_scan_smoke.sh            # local docker-compose stack
#   TARGET=prod scripts/smoke/thematic_scan_smoke.sh
#
# Env overrides:
#   TARGET=local|prod         (default local)
#   HOST                      OpenWebUI base URL    (local: http://localhost:3333,  prod: https://chatbot.datameesters.nl)
#   SKILLS_URL                rm-skills base URL    (local: http://localhost:4101,  prod: not externally exposed)
#   MEMORY_MCP_URL            rm-mcp-memory base    (local: http://localhost:3210,  prod: https://mcp.datameesters.nl/memory/mcp)
#   SKILLS_MCP_URL            rm-mcp-skills base    (local: http://localhost:3399,  prod: https://mcp.datameesters.nl/skills/mcp)
#   APP_CONTAINER=rm-chatbot
#   DB_CONTAINER=rm-chatbot-db
#   ADMIN_USER_ID             defaults to first admin in DB
#   PERSONA=ro-assistent      model id to use
#   GEMEENTE_CODE=GM0344      Utrecht
#   THEMA_SLUG=energietransitie
#   STRICT=0                  set to 1 to fail on soft warnings
#
# Exit codes:
#   0  all stages pass (strict mode: all hard + soft)
#   1  stage 1 (services) failed
#   2  stage 2 (skill injection) failed
#   3  stage 3 (project binding) failed
#   4  stage 4 (output canon) failed
#   5  setup / auth failure

set -uo pipefail

TARGET="${TARGET:-local}"
case "$TARGET" in
  local)
    HOST="${HOST:-http://localhost:3333}"
    SKILLS_URL="${SKILLS_URL:-http://localhost:4101}"
    MEMORY_MCP_URL="${MEMORY_MCP_URL:-http://localhost:3210}"
    SKILLS_MCP_URL="${SKILLS_MCP_URL:-http://localhost:3399}"
    ;;
  prod)
    HOST="${HOST:-https://chatbot.datameesters.nl}"
    SKILLS_URL="${SKILLS_URL:-}"  # rm-skills not externally exposed in prod
    MEMORY_MCP_URL="${MEMORY_MCP_URL:-https://mcp.datameesters.nl/memory/mcp}"
    SKILLS_MCP_URL="${SKILLS_MCP_URL:-https://mcp.datameesters.nl/skills/mcp}"
    ;;
  *)
    echo "Unknown TARGET=$TARGET (expected local|prod)" >&2
    exit 5
    ;;
esac

APP_CONTAINER="${APP_CONTAINER:-rm-chatbot}"
DB_CONTAINER="${DB_CONTAINER:-rm-chatbot-db}"
PERSONA="${PERSONA:-ro-assistent}"
GEMEENTE_CODE="${GEMEENTE_CODE:-GM0344}"
THEMA_SLUG="${THEMA_SLUG:-energietransitie}"
STRICT="${STRICT:-0}"
EXPECTED_PROJECT_ID="beleidsscan:${GEMEENTE_CODE}:${THEMA_SLUG}"

# Color output, only when stdout is a tty.
if [ -t 1 ]; then
  C_OK=$'\033[32m'; C_FAIL=$'\033[31m'; C_WARN=$'\033[33m'; C_DIM=$'\033[2m'; C_END=$'\033[0m'
else
  C_OK=""; C_FAIL=""; C_WARN=""; C_DIM=""; C_END=""
fi

pass()  { echo "${C_OK}PASS${C_END} $*"; }
fail()  { echo "${C_FAIL}FAIL${C_END} $*" >&2; }
warn()  { echo "${C_WARN}WARN${C_END} $*" >&2; }
info()  { echo "${C_DIM}info${C_END} $*"; }

SOFT_FAILS=0

soft_assert() {
  local cond="$1"; shift
  if eval "$cond"; then
    pass "$*"
  else
    warn "$*"
    SOFT_FAILS=$((SOFT_FAILS + 1))
  fi
}

# ----------------------------------------------------------------------------
# Stage 1 — services reachable
# ----------------------------------------------------------------------------
stage1() {
  echo "${C_DIM}== Stage 1: services reachable ==${C_END}"
  local fails=0

  # Chatbot API
  if curl -sf -o /dev/null --max-time 5 "$HOST/api/health"; then
    pass "chatbot /api/health"
  else
    fail "chatbot /api/health unreachable ($HOST)"; fails=$((fails+1))
  fi

  # rm-skills (only checked in local — not externally exposed in prod)
  if [ -n "$SKILLS_URL" ]; then
    if curl -sf -o /dev/null --max-time 5 "$SKILLS_URL/health" \
      || curl -sf -o /dev/null --max-time 5 "$SKILLS_URL/api/v1/skills"; then
      pass "rm-skills reachable at $SKILLS_URL"
    else
      fail "rm-skills unreachable at $SKILLS_URL"; fails=$((fails+1))
    fi
  fi

  # MCP servers — /health is unauthenticated
  if curl -sf -o /dev/null --max-time 5 "$MEMORY_MCP_URL/health" \
    || curl -sf -o /dev/null --max-time 5 "${MEMORY_MCP_URL%/mcp}/health"; then
    pass "rm-mcp-memory /health"
  else
    fail "rm-mcp-memory /health unreachable"; fails=$((fails+1))
  fi

  if curl -sf -o /dev/null --max-time 5 "$SKILLS_MCP_URL/health" \
    || curl -sf -o /dev/null --max-time 5 "${SKILLS_MCP_URL%/mcp}/health"; then
    pass "rm-mcp-skills /health"
  else
    fail "rm-mcp-skills /health unreachable"; fails=$((fails+1))
  fi

  return "$fails"
}

# ----------------------------------------------------------------------------
# Stage setup — mint admin JWT
# ----------------------------------------------------------------------------
mint_token() {
  if [ -n "${WEBUI_TOKEN:-}" ]; then
    echo "$WEBUI_TOKEN"
    return 0
  fi

  ADMIN_USER_ID="${ADMIN_USER_ID:-}"
  if [ -z "$ADMIN_USER_ID" ]; then
    ADMIN_USER_ID=$(docker exec "$DB_CONTAINER" psql -U rmchatbot -d rmchatbot -tAc \
      "SELECT id FROM \"user\" WHERE role = 'admin' ORDER BY created_at LIMIT 1;" 2>/dev/null \
      | tr -d '[:space:]')
  fi
  [ -z "$ADMIN_USER_ID" ] && return 1

  docker exec -i -e ADMIN_USER_ID="$ADMIN_USER_ID" "$APP_CONTAINER" python3 - <<'PY' 2>/dev/null | tail -1
import os
from datetime import timedelta
from open_webui.utils.auth import create_token
print(create_token({'id': os.environ['ADMIN_USER_ID']}, timedelta(minutes=15)))
PY
}

# ----------------------------------------------------------------------------
# Stage 2 — skill injection visible in logs
# ----------------------------------------------------------------------------
stage2() {
  echo "${C_DIM}== Stage 2: skill injection ==${C_END}"
  local fails=0

  # Truncate log marker so we only look at our own request.
  local marker; marker="smoke-$(date +%s)-$$"

  local payload
  payload=$(cat <<JSON
{
  "model": "$PERSONA",
  "messages": [
    {"role": "user", "content": "[$marker] doe een thematische beleidsscan voor gemeente Utrecht op thema energietransitie"}
  ],
  "stream": false
}
JSON
)

  local resp
  resp=$(curl -sS --max-time 90 \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$HOST/api/chat/completions" || true)

  if [ -z "$resp" ]; then
    fail "no response from chat/completions"; return 1
  fi

  CHAT_ID=$(echo "$resp" | jq -r '.id // empty')
  RESPONSE_TEXT=$(echo "$resp" | jq -r '.choices[0].message.content // empty')

  if [ -z "$RESPONSE_TEXT" ]; then
    fail "response has no assistant content"; echo "$resp" | head -c 500 >&2; return 1
  fi
  pass "chat completion returned ($(echo -n "$RESPONSE_TEXT" | wc -c) chars)"

  # Check filter logs for skill injection. Local only; prod logs require shell on Hetzner.
  if [ "$TARGET" = "local" ]; then
    local log_window=60
    if docker logs --since "${log_window}s" "$APP_CONTAINER" 2>&1 \
      | grep -q "skills_context"; then
      pass "skills_context filter fired (docker logs)"
    else
      fail "skills_context filter did NOT fire in last ${log_window}s"
      fails=$((fails+1))
    fi

    if docker logs --since "${log_window}s" "$APP_CONTAINER" 2>&1 \
      | grep -q "beleidsscan"; then
      pass "beleidsscan skill referenced in filter logs"
    else
      warn "beleidsscan not seen in filter logs — may indicate mandatory:true missing on the skill"
      SOFT_FAILS=$((SOFT_FAILS+1))
    fi
  else
    info "prod target — log inspection skipped (run on Hetzner host to verify)"
  fi

  return "$fails"
}

# ----------------------------------------------------------------------------
# Stage 3 — active project binding
# ----------------------------------------------------------------------------
stage3() {
  echo "${C_DIM}== Stage 3: active project binding ==${C_END}"

  if [ -z "${CHAT_ID:-}" ]; then
    warn "no chat id captured from Stage 2 — skipping"
    SOFT_FAILS=$((SOFT_FAILS+1))
    return 0
  fi

  # Call get_active_project MCP tool via the memory MCP endpoint.
  local mcp_payload
  mcp_payload=$(cat <<JSON
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_active_project","arguments":{}}}
JSON
)

  local mcp_resp
  mcp_resp=$(curl -sS --max-time 10 \
    -H "Authorization: Bearer ${MEMORY_MCP_TOKEN:-$TOKEN}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "X-Thread-Id: $CHAT_ID" \
    -d "$mcp_payload" \
    "$MEMORY_MCP_URL/mcp" 2>&1 || true)

  local project_id
  project_id=$(echo "$mcp_resp" \
    | sed -n 's/^data: //p; t; p' \
    | jq -r '.result.content[0].text // empty' 2>/dev/null \
    | jq -r '.project_id // empty' 2>/dev/null || echo "")

  soft_assert "[ \"$project_id\" = \"$EXPECTED_PROJECT_ID\" ]" \
    "active project = $EXPECTED_PROJECT_ID (got: '$project_id')"

  return 0
}

# ----------------------------------------------------------------------------
# Stage 4 — output follows beleidsscan canon
# ----------------------------------------------------------------------------
stage4() {
  echo "${C_DIM}== Stage 4: output canon ==${C_END}"
  local fails=0

  if [ -z "${RESPONSE_TEXT:-}" ]; then
    fail "no response text from Stage 2"; return 1
  fi

  local len; len=$(echo -n "$RESPONSE_TEXT" | wc -c)
  if [ "$len" -gt 500 ]; then
    pass "response length $len > 500"
  else
    fail "response too short ($len chars) — likely refusal"
    fails=$((fails+1))
  fi

  # Dutch language heuristic — count common Dutch words.
  local dutch_hits
  dutch_hits=$(echo "$RESPONSE_TEXT" | grep -oiE '\b(de|het|een|en|van|voor|aan|bij|op|met|gemeente|beleid|scan|thema)\b' | wc -l)
  if [ "$dutch_hits" -gt 10 ]; then
    pass "Dutch language ($dutch_hits common-word hits)"
  else
    fail "response not in Dutch ($dutch_hits common-word hits)"
    fails=$((fails+1))
  fi

  # Step-marker check — extract from SKILL.md at runtime so the smoke tracks canon edits.
  # The skill in rm-skills lives at /skills/beleidsscan/SKILL.md (mounted into rm-skills container).
  local skill_md=""
  if [ -n "$SKILLS_URL" ]; then
    skill_md=$(curl -sS --max-time 5 "$SKILLS_URL/api/v1/skills/beleidsscan" 2>/dev/null \
      | jq -r '.skill_md // empty')
  fi

  if [ -n "$skill_md" ]; then
    # Crude marker extraction: headings that look like "## Stap N" / "## Phase N" / etc.
    local markers
    markers=$(echo "$skill_md" | grep -oiE '^#+\s+(stap|phase|fase|step)\s+[0-9]' | head -10)
    local marker_count; marker_count=$(echo "$markers" | grep -cv '^$' || true)
    if [ "$marker_count" -gt 0 ]; then
      local hits=0
      while IFS= read -r m; do
        local norm; norm=$(echo "$m" | sed -E 's/^#+\s+//')
        if echo "$RESPONSE_TEXT" | grep -qi "$norm"; then
          hits=$((hits+1))
        fi
      done <<< "$markers"
      soft_assert "[ $hits -ge $((marker_count - 1)) ]" \
        "response references $hits/$marker_count canon step markers"
    else
      warn "no step markers extracted from SKILL.md — heuristic miss"
      SOFT_FAILS=$((SOFT_FAILS+1))
    fi
  else
    info "SKILL.md not fetchable (no SKILLS_URL or prod) — marker check skipped"
  fi

  return "$fails"
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
echo "${C_DIM}target=$TARGET host=$HOST persona=$PERSONA project=$EXPECTED_PROJECT_ID${C_END}"
echo

stage1; s1=$?
if [ "$s1" -ne 0 ]; then echo; fail "Stage 1 failed ($s1 services down)"; exit 1; fi
echo

TOKEN=$(mint_token)
if [ -z "$TOKEN" ]; then
  fail "could not mint admin token"
  exit 5
fi

stage2; s2=$?
if [ "$s2" -ne 0 ]; then echo; fail "Stage 2 failed"; exit 2; fi
echo

stage3
echo

stage4; s4=$?
if [ "$s4" -ne 0 ]; then echo; fail "Stage 4 failed"; exit 4; fi
echo

if [ "$SOFT_FAILS" -gt 0 ]; then
  if [ "$STRICT" = "1" ]; then
    fail "$SOFT_FAILS soft assertions failed (STRICT=1)"; exit 3
  else
    warn "$SOFT_FAILS soft assertions failed (set STRICT=1 to fail)"
  fi
fi

pass "all stages passed"
exit 0
