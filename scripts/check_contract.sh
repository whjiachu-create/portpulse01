#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"

need_path() {
  local p="$1"
  curl -s "$BASE/openapi.json" | jq -er --arg p "$p" '.paths[$p]' >/dev/null
}

# 路由存在性
need_path "/v1/meta/sources"
need_path "/v1/ports/{unlocode}/overview"
need_path "/v1/ports/{unlocode}/trend"
need_path "/v1/health"

# 概览 CSV 的缓存/ETag/HEAD 语义
UNLOCODE="${UNLOCODE:-USLAX}"
API_HEADER="${API_HEADER:-X-API-Key: dev_key_123}"
CSV="$BASE/v1/ports/$UNLOCODE/overview?format=csv"
H="$(curl -sSI -H "$API_HEADER" "$CSV")"
echo "$H" | awk 'BEGIN{IGNORECASE=1}/^(HTTP|etag:|cache-control:)/{gsub(/\r/,"");print}'
ET=$(echo "$H" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r/,"");print $2}')
[[ -n "$ET" ]] || { echo "Missing ETag"; exit 1; }
[[ "$ET" != W/* ]] || { echo "Weak ETag"; exit 1; }
curl -sS -D - -o /dev/null -H "$API_HEADER" -H "If-None-Match: $ET" "$CSV" | sed -n '1p' | grep -q "304"
curl -sSI -H "$API_HEADER" "$CSV" | awk 'BEGIN{IGNORECASE=1}/^HTTP/{print}' | grep -q "200"
curl -sSI -H "$API_HEADER" "$CSV" | awk 'BEGIN{IGNORECASE=1}/^cache-control:/{print}' | grep -qi "max-age="