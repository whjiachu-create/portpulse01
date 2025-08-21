#!/usr/bin/env bash
# scripts/selfcheck.sh (v3)
# - 双阈值：服务端阈值(SLOW_SERVER_MS)硬门槛；端到端阈值(SLOW_E2E_MS)仅告警
# - 任何接口服务端耗时>=阈值 或 HTTP!=200 -> 退出非0

set -u

: "${BASE_URL:?BASE_URL not set}"
: "${API_KEY:?API_KEY not set}"

SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # 服务端阈值（看 x-response-time-ms）
SLOW_E2E_MS="${SLOW_E2E_MS:-2500}"        # 端到端阈值（仅告警）

green(){ printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
red(){ printf '\033[31m%s\033[0m\n' "$*"; }

measure() {
  # $1 name, $2 url, [extra curl args...]
  local name="$1" url="$2"; shift 2 || true
  # 抓响应头 + 端到端耗时
  local headers tmp; tmp="$(mktemp)"
  read -r code t < <(curl -sS -D "$tmp" -o /dev/null -H "Accept: application/json" "$@" \
                     -w '%{http_code} %{time_total}' "$url")
  # 端到端 ms
  local e2e_ms; e2e_ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  # 服务端 ms（响应头）
  local server_ms=""; server_ms=$(grep -i '^x-response-time-ms:' "$tmp" | awk '{print $2}' | tr -d '\r')
  rm -f "$tmp"

  if [ "$code" != "200" ]; then
    red "✗ $name  HTTP $code (e2e=${e2e_ms}ms, server=${server_ms:-NA}ms)"
    return 2
  fi

  # 端到端仅告警
  if [ "$e2e_ms" -ge "$SLOW_E2E_MS" ]; then
    yellow "! $name  slow E2E=${e2e_ms}ms (>=${SLOW_E2E_MS}ms)"
    e2e_warn=1
  else
    green "✓ $name  E2E=${e2e_ms}ms"
  fi

  # 服务端硬门槛（没有该头则不拦截，只提示）
  if [ -n "$server_ms" ]; then
    if [ "$server_ms" -ge "$SLOW_SERVER_MS" ]; then
      red "✗ $name  server=${server_ms}ms (>=${SLOW_SERVER_MS}ms)"
      return 2
    fi
  else
    yellow "! $name  no x-response-time-ms header"
  fi

  return 0
}

measure_csv() {
  # 同上，但校验表头
  local name="$1" url="$2" expect="$3"; shift 3 || true
  local tmp headfile; tmp="$(mktemp)"; headfile="$(mktemp)"
  read -r code t < <(curl -sS -D "$headfile" -o "$tmp" "$@" -w '%{http_code} %{time_total}' "$url")
  local e2e_ms; e2e_ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  local server_ms=""; server_ms=$(grep -i '^x-response-time-ms:' "$headfile" | awk '{print $2}' | tr -d '\r')
  local head; head="$(head -n1 "$tmp" | tr -d '\r')"
  rm -f "$tmp" "$headfile"

  if [ "$code" != "200" ]; then
    red "✗ $name  HTTP $code (e2e=${e2e_ms}ms, server=${server_ms:-NA}ms)"
    return 2
  fi
  if [[ "$head" != "$expect"* ]]; then
    red "✗ $name  bad header '${head}'"
    return 2
  fi

  if [ "$e2e_ms" -ge "$SLOW_E2E_MS" ]; then
    yellow "! $name  slow E2E=${e2e_ms}ms (>=${SLOW_E2E_MS}ms)"
    e2e_warn=1
  else
    green "✓ $name  E2E=${e2e_ms}ms"
  fi

  if [ -n "$server_ms" ] && [ "$server_ms" -ge "$SLOW_SERVER_MS" ]; then
    red "✗ $name  server=${server_ms}ms (>=${SLOW_SERVER_MS}ms)"
    return 2
  fi

  return 0
}

echo "🔎 Selfcheck @ ${BASE_URL}  (server<${SLOW_SERVER_MS}ms, e2e warn >=${SLOW_E2E_MS}ms)"

fail=0
e2e_warn=0

measure "/v1/health"                            "${BASE_URL}/v1/health" || fail=1
measure "/v1/sources"                           "${BASE_URL}/v1/sources" || fail=1
measure "/v1/ports/USLAX/snapshot"              "${BASE_URL}/v1/ports/USLAX/snapshot" -H "X-API-Key: ${API_KEY}" || fail=1
measure "/v1/ports/USLAX/dwell?days=14"         "${BASE_URL}/v1/ports/USLAX/dwell?days=14" -H "X-API-Key: ${API_KEY}" || fail=1
measure_csv "/v1/ports/USLAX/overview?format=csv" "${BASE_URL}/v1/ports/USLAX/overview?format=csv" 'unlocode,as_of' -H "X-API-Key: ${API_KEY}" || fail=1
measure "/v1/ports/USNYC/alerts?window=14d"     "${BASE_URL}/v1/ports/USNYC/alerts?window=14d" -H "X-API-Key: ${API_KEY}" || fail=1
measure "/v1/ports/USLAX/trend"                 "${BASE_URL}/v1/ports/USLAX/trend?days=30&fields=vessels,avg_wait_hours&limit=30&offset=0" -H "X-API-Key: ${API_KEY}" || fail=1

[ "$fail" -eq 0 ] && echo "✅ Server OK (under ${SLOW_SERVER_MS}ms)."
[ "$e2e_warn" -ne 0 ] && echo "⚠️  Some endpoints are network-slow (E2E >= ${SLOW_E2E_MS}ms)."

exit "$fail"