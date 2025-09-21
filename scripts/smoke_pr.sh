#!/usr/bin/env bash
KEY="${KEY:-DEMO_KEY}"
set -euo pipefail
KEY="${KEY:-pp_dev_123456}"
if ! command -v jq >/dev/null; then sudo apt-get update -y && sudo apt-get install -y jq; fi

BASE="${BASE:-http://127.0.0.1:8080}"
UNLOCODE="${UNLOCODE:-USLAX}"
API_HEADER="${API_HEADER:-X-API-Key: ${KEY}}"
export PP_DEMO_KEY="$KEY" PP_VALID_KEYS="$KEY" PORTPULSE_DEMO_KEY="$KEY" PORTPULSE_API_KEYS="$KEY"

log() { printf "\n== %s ==\n" "$*"; }

export PP_DEMO_KEY="${KEY}" PP_VALID_KEYS="${KEY}" PORTPULSE_DEMO_KEY="${KEY}" PORTPULSE_API_KEYS="${KEY}"
start_server() {
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 > uvicorn.log 2>&1 &
  PID=$!
  trap 'kill ${PID:-0} 2>/dev/null || true' EXIT
  for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/v1/health" || true)
    [ "$code" = "200" ] && return 0
    sleep 0.5
  done
  echo "Healthcheck timeout"; tail -n 100 uvicorn.log || true; exit 1
}

has_path() {
  local p="$1"
  curl -s "$BASE/openapi.json" | jq -er --arg p "$p" '.paths[$p]' >/dev/null 2>&1
}

require_header_contains() {
  local headers="$1" key_lc="$2" expect_sub="$3"
  echo "$headers" | awk 'BEGIN{IGNORECASE=1} /^'"$key_lc"':/ {print}' | grep -qi -- "$expect_sub"
}

require_status() {
  local expect="$1" url="$2"; shift 2 || true
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "$@" "$url")"
  [ "$code" = "$expect" ] || { echo "Expect $expect but got $code: $url"; return 1; }
}

main() {
  start_server

  log "health"
  H="$(curl -sS -D - -o /dev/null "$BASE/v1/health")"
  echo "$H" | sed -n '1,12p'
  if ! require_header_contains "$H" "cache-control" "no-store"; then echo "WARN: health lacks Cache-Control: no-store"; fi

  if has_path "/v1/ports/{unlocode}/overview"; then
    log "overview csv（强 ETag + 304 + HEAD）"
    CSV="$BASE/v1/ports/$UNLOCODE/overview?format=csv"
    H1="$(curl -sSI -H "$API_HEADER" "$CSV")"
    echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^(HTTP|etag:|cache-control:|vary:|x-csv-source:)/{gsub(/\r/,"");print}'
    ETAG="$(echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r/,"");print $2}')"
    [ -n "$ETAG" ] || { echo "Missing ETag"; echo "$H1" | sed -n "1,60p"; exit 1; }
    case "$ETAG" in W/*) echo "Weak ETag ($ETAG)"; exit 1 ;; esac
    require_status 304 "$CSV" -H "$API_HEADER" -H "If-None-Match: $ETAG"
    STRONG="${ETAG#W/}"
    require_status 304 "$CSV" -H "$API_HEADER" -H "If-None-Match: W/$STRONG"
    H2="$(curl -sSI -H "$API_HEADER" "$CSV")"
    echo "$H2" | sed -n '1,10p'
    echo "$H2" | awk 'BEGIN{IGNORECASE=1}/^HTTP/{print $0; exit}' | grep -q "200" || { echo "HEAD not 200"; exit 1; }
    require_header_contains "$H2" "etag" '"'
    require_header_contains "$H2" "cache-control" "max-age="
  else
    log "跳过 ports/overview（OpenAPI 未暴露此路由）"
  fi

  echo; echo "All PR smoke checks passed."
}
main "$@"
