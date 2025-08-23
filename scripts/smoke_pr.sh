#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8080}"
UNLOCODE="${UNLOCODE:-USLAX}"
API_HEADER="${API_HEADER:-X-API-Key: dev_key_123}"

log() { printf "\n== %s ==\n" "$*"; }

start_server() {
  # 用 python -m 更稳（避免 PATH 中 uvicorn 解析问题）
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 > uvicorn.log 2>&1 &
  PID=$!
  trap 'kill ${PID:-0} 2>/dev/null || true' EXIT

  # 等待健康就绪（30s超时）
  for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/v1/health" || true)
    if [ "$code" = "200" ]; then
      return 0
    fi
    sleep 0.5
  done

  echo "Healthcheck timeout. Tail uvicorn.log:"
  tail -n 100 uvicorn.log || true
  exit 1
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
  if [ "$code" != "$expect" ]; then
    echo "Expect $expect but got $code for: $url"
    return 1
  fi
}

main() {
  start_server

  log "health"
  H="$(curl -sS -D - -o /dev/null "$BASE/v1/health")"
  echo "$H" | sed -n '1p'
  require_header_contains "$H" "cache-control" "no-store"

  # 仅当存在 /v1/ports/{unlocode}/overview 时，才做 CSV 强ETag/304/HEAD 测试
  if has_path "/v1/ports/{unlocode}/overview"; then
    log "overview csv（强 ETag + 304 + HEAD）"
    CSV="$BASE/v1/ports/$UNLOCODE/overview?format=csv"

    H1="$(curl -sSI -H "$API_HEADER" "$CSV")"
    echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^(HTTP|etag:|cache-control:|vary:|x-csv-source:)/{gsub(/\r/,"");print}'
    # 取 ETag
    ETAG="$(echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r/,"");print $2}')"
    test -n "$ETAG" || { echo "Missing ETag"; exit 1; }
    case "$ETAG" in
      W/*) echo "ETag is weak ($ETAG), expect strong"; exit 1 ;;
    esac
    # 304 校验（强/弱包装都应 304）
    require_status 304 "$CSV" -H "$API_HEADER" -H "If-None-Match: $ETAG"
    STRONG="${ETAG#W/}"
    require_status 304 "$CSV" -H "$API_HEADER" -H "If-None-Match: W/$STRONG"

    # HEAD 200 + 仅响应头
    H2="$(curl -sSI -H "$API_HEADER" "$CSV")"
    echo "$H2" | sed -n '1,10p'
    echo "$H2" | awk 'BEGIN{IGNORECASE=1}/^HTTP/{print $0; exit}' | grep -q "200" || { echo "HEAD not 200"; exit 1; }
    require_header_contains "$H2" "etag" '"'
    require_header_contains "$H2" "cache-control" "max-age="
  else
    log "跳过 ports/overview 测试（OpenAPI 未暴露此路由）"
  fi

  echo; echo "All PR smoke checks passed."
}

main "$@"