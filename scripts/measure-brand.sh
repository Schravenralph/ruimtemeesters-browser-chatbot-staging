#!/usr/bin/env bash
# Measure brand-pass-2 criteria against a running rm-chatbot.
# Outputs JSON to stdout.
#
# Usage:
#   scripts/measure-brand.sh > product-docs/superpowers/specs/2026-04-17-brand-pass-2-baseline.json

set -u
HOST="${BRAND_MEASURE_HOST:-http://localhost:3333}"
DB_CONTAINER="${BRAND_MEASURE_DB:-rm-chatbot-db}"
APP_CONTAINER="${BRAND_MEASURE_APP:-rm-chatbot}"
ADMIN_USER_ID="${BRAND_MEASURE_ADMIN_ID:-5d5463ce-bf33-4259-9611-6ec031f184a7}"

A_CT=$(curl -sI "$HOST/brand-assets/icon-blue.png" | awk '/^content-type:/ {print tolower($2)}' | tr -d '\r' | head -1)
A_CODE=$(curl -s -o /dev/null -w '%{http_code}' "$HOST/brand-assets/icon-blue.png")

MANIFEST=$(curl -s "$HOST/manifest.json")

TOKEN=$(docker exec "$APP_CONTAINER" python3 -c "
from open_webui.utils.auth import create_token
from datetime import timedelta
print(create_token({'id': '$ADMIN_USER_ID'}, timedelta(minutes=5)))
" 2>/dev/null | tail -1)

CONFIG=$(curl -s "$HOST/api/v1/configs" -H "Authorization: Bearer $TOKEN")

E_COUNT=$(docker exec "$DB_CONTAINER" psql -U rmchatbot -d rmchatbot -tAc \
  "SELECT COUNT(DISTINCT meta::jsonb->'profile_image_url') FROM model WHERE id LIKE 'rm-%';" 2>/dev/null | tr -d ' ')

HAS_GREETING_UTIL="false"; [ -f src/lib/utils/greeting.ts ] && HAS_GREETING_UTIL="true"
HAS_ABOUT_COPY="false"; grep -q "Gebouwd op Open WebUI" src/lib/components/chat/SettingsModal.svelte 2>/dev/null && HAS_ABOUT_COPY="true"
HAS_SEED_SCRIPT="false"; [ -x scripts/seed-gemini-connection.sh ] && HAS_SEED_SCRIPT="true"

export A_CT A_CODE MANIFEST CONFIG E_COUNT HAS_GREETING_UTIL HAS_ABOUT_COPY HAS_SEED_SCRIPT HOST

python3 <<'PYEOF'
import json, os, datetime

manifest_txt = os.environ.get("MANIFEST", "{}")
try:
    manifest = json.loads(manifest_txt)
except Exception:
    manifest = {}

config_txt = os.environ.get("CONFIG", "{}")
try:
    config = json.loads(config_txt)
except Exception:
    config = {}

# A
a_ct = os.environ.get("A_CT", "")
a_code = os.environ.get("A_CODE", "")
a_pass = a_ct == "image/png" and a_code == "200"

# B
b_bg = manifest.get("background_color", "")
b_icons = manifest.get("icons", [])
b_icon = b_icons[0].get("src", "") if b_icons else ""
b_name = manifest.get("name", "")
b_pass = (
    b_bg in ("#F7F4EF", "#161620")
    and b_icon.startswith("/brand-assets/")
    and "Open WebUI" not in b_name
)

# C — banner
banners = (config.get("ui", {}).get("banners") or config.get("banners") or [])
c_pass = any(
    "Besloten werkomgeving voor Ruimtemeesters" in (b.get("content", "") if isinstance(b, dict) else "")
    for b in banners
)

# D — greeting util file
d_pass = os.environ.get("HAS_GREETING_UTIL") == "true"

# E — distinct assistant avatars
e_count_s = os.environ.get("E_COUNT", "0")
try:
    e_count = int(e_count_s)
except Exception:
    e_count = 0
e_pass = e_count == 5

# F — ENABLE_COMMUNITY_SHARING
f_val = None
for path in [("features", "enable_community_sharing"), ("enable_community_sharing",)]:
    cur = config
    ok = True
    for k in path:
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            ok = False
            break
    if ok:
        f_val = cur
        break
f_pass = f_val is False

# G — default model
g_dm = (
    config.get("default_models")
    or config.get("ui", {}).get("default_models")
    or ""
)
g_pass = g_dm == "gemini.gemini-2.5-flash-lite"

# H — about copy
h_pass = os.environ.get("HAS_ABOUT_COPY") == "true"

# I — seed script
i_pass = os.environ.get("HAS_SEED_SCRIPT") == "true"

out = {
    "timestamp": datetime.datetime.now().astimezone().isoformat(),
    "host": os.environ.get("HOST"),
    "criteria": {
        "A_favicon_content_type_and_200": {"ct": a_ct, "code": a_code, "pass": a_pass},
        "B_manifest_branded": {"background_color": b_bg, "icon": b_icon, "name": b_name, "pass": b_pass},
        "C_banner_present": {"pass": c_pass},
        "D_greeting_util_file": {"pass": d_pass},
        "E_distinct_assistant_avatars": {"count": e_count, "pass": e_pass},
        "F_community_sharing_disabled": {"value": f_val, "pass": f_pass},
        "G_default_model_gemini_flash_lite": {"value": g_dm, "pass": g_pass},
        "H_about_modal_rm_copy": {"pass": h_pass},
        "I_seed_script_exists": {"pass": i_pass},
    },
}
print(json.dumps(out, indent=2))
PYEOF
