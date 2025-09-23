#!/usr/bin/env bash
set -euo pipefail

# --- 基本环境 ---
BASE="${BASE:-http://127.0.0.1:8080}"
PORT="${UNLOCODE:-${PORT:-USLAX}}"
API_KEY="${API_KEY:-${PORTPULSE_API_KEY:-${KEY:-${NEXT_PUBLIC_DEMO_API_KEY:-dev_demo_123}}}}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ need $1"; exit 1; }; }
need curl; need jq

ok()   { printf "✅ %s\n" "$1"; }
warn() { printf "⚠️  %s\n" "$1"; }
fail() { printf "❌ %s\n" "$1"; exit 1; }

echo "=== PortPulse PR Smoke ==="
echo "BASE=$BASE PORT=$PORT"

# --- 起本地 Uvicorn（若没起） ---
uvicorn_pid=""
if ! curl -fsS "$BASE/v1/health" >/dev/null 2>&1; then
  # 在 repo 根目录下以后台方式启动
  nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 > /tmp/uvicorn.log 2>&1 &
  uvicorn_pid=$!
  trap '[[ -n "${uvicorn_pid:-}" ]] && kill $uvicorn_pid 2>/dev/null || true' EXIT
fi

# --- 健康探活，最多等 25s ---
for i in {1..25}; do
  if curl -fsS "$BASE/v1/health" | jq -e '.ok==true' >/dev/null 2>&1; then
    ok "health ready"
    break
  fi
  sleep 1
  [[ $i -eq 25 ]] && { echo "---- /tmp/uvicorn.log ----"; tail -n +1 /tmp/uvicorn.log || true; fail "Healthcheck timeout"; }
done

# --- OpenAPI / 根路径 ---
TITLE=$(curl -fsS "$BASE/openapi.json" | jq -r '.info.title')
VER=$(curl -fsS "$BASE/openapi.json" | jq -r '.info.version')
PCNT=$(curl -fsS "$BASE/openapi.json" | jq '(.paths|length)')
echo "OpenAPI: $TITLE v$VER paths=$PCNT"
[[ "$PCNT" -ge 10 ]] && ok "OpenAPI paths >=10" || warn "OpenAPI paths <10 (=$PCNT)"

code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE")
[[ "$code" =~ ^(200|301|302|307|308)$ ]] && ok "/ root reachable ($code)" || warn "/ root http=$code"

# --- 受保护端点（用 X-API-Key；CI 默认 demo key 只读） ---
curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=json" \
  | jq -e '.unlocode and has("avg_wait_hours")' >/dev/null && ok "overview JSON OK" || fail "overview JSON failed"

curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=csv" \
  | head -n 1 | grep -qiE '^unlocode,' && ok "overview CSV header OK" || fail "overview CSV header failed"

LEN=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/trend?limit=7&format=json" | jq '.points | length')
[[ "$LEN" -ge 1 ]] && ok "trend JSON points length=$LEN" || fail "trend JSON points invalid"

# ETag / 304
H=$(curl -fsS -D - -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/trend?limit=7&format=csv" -o /dev/null)
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1} /^etag:/{gsub(/\r|\"/,"");print $2}')
[[ -n "$ET" ]] || fail "ETag not found"
code=$(curl -s -w "%{http_code}" -o /dev/null -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/$PORT/trend?limit=7&format=csv")
[[ "$code" == "304" ]] && ok "ETag 304 hit" || warn "ETag not 304 (http=$code)"

HITS=0; TOTAL=10
for i in $(seq 1 $TOTAL); do
  rc=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$ET\"" \
    "$BASE/v1/ports/$PORT/trend?limit=7&format=csv")
  [[ "$rc" == "304" ]] && HITS=$((HITS+1))
done
echo "ETag 304 hit-rate: $HITS/$TOTAL"

unauth=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/ports/$PORT/overview")
[[ "$unauth" =~ ^(401|403)$ ]] && ok "Unauthorized check ($unauth)" || warn "Unauthorized http=$unauth"

echo "=== Done ==="