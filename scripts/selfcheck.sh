#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://api.useportpulse.com}"
PORT="${PORT:-USLAX}"
API_KEY="${API_KEY:-}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ need $1"; exit 1; }; }
need curl; need jq; need awk

ok() { printf "✅ %s\n" "$1"; }
warn() { printf "⚠️  %s\n" "$1"; }
fail() { printf "❌ %s\n" "$1"; exit 1; }

echo "=== PortPulse Selfcheck ==="
echo "BASE=$BASE PORT=$PORT"

curl -fsS "$BASE/v1/health" | jq -e 'has("ok") and .ok==true' >/dev/null && ok "/v1/health OK" || fail "/v1/health failed"

TITLE=$(curl -fsS "$BASE/openapi.json" | jq -r '.info.title')
VER=$(curl -fsS "$BASE/openapi.json" | jq -r '.info.version')
PCNT=$(curl -fsS "$BASE/openapi.json" | jq '(.paths|length)')
echo "OpenAPI: $TITLE v$VER paths=$PCNT"
[[ "$PCNT" -ge 10 ]] && ok "OpenAPI paths >=10" || warn "OpenAPI paths <10 (=$PCNT)"

code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE")
[[ "$code" =~ ^(200|301|302|307|308)$ ]] && ok "/ root reachable ($code)" || warn "/ root http=$code"

if [[ -z "$API_KEY" ]]; then
  warn "API_KEY 为空，跳过受保护端点；export API_KEY=pp_live_xxx 后重跑"
  exit 0
fi

curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=json" \
  | jq -e '.unlocode and has("avg_wait_hours")' >/dev/null && ok "overview JSON OK" || fail "overview JSON failed"

curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=csv" \
  | head -n 1 | grep -qiE '^unlocode,' && ok "overview CSV header OK" || fail "overview CSV header failed"

LEN=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/trend?limit=7&format=json" | jq '.points | length')
[[ "$LEN" -ge 1 ]] && ok "trend JSON points length=$LEN" || fail "trend JSON points invalid"

H=$(curl -fsS -D - -H "X-API-Key: $API_KEY" \
  "$BASE/v1/ports/$PORT/trend?limit=7&format=csv" -o /dev/null)
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1} /^etag:/{gsub(/\r|\"/,"");print $2}')
[[ -n "$ET" ]] || fail "ETag not found"
code=$(curl -s -w "%{http_code}" -o /dev/null \
  -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/$PORT/trend?limit=7&format=csv")
if [[ "$code" == "304" ]]; then ok "ETag 304 hit"; else warn "ETag not 304 (http=$code)"; fi

# ETag strong-equality hit-rate (10 samples)
HITS=0; TOTAL=10
for i in $(seq 1 $TOTAL); do
  rc=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$ET\"" \
    "$BASE/v1/ports/$PORT/trend?limit=7&format=csv")
  [[ "$rc" == "304" ]] && HITS=$((HITS+1))
done
echo "ETag 304 hit-rate: $HITS/$TOTAL"

unauth=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/ports/$PORT/overview")
[[ "$unauth" =~ ^(401|403)$ ]] && ok "Unauthorized check ($unauth)" || warn "Unauthorized http=$unauth"

echo "=== Done ==="
