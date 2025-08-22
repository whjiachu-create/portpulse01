#!/usr/bin/env bash
# scripts/health_gate.sh (hardened & tolerant)
# 规则：连续 PASS_COUNT 次满足以下条件之一即通过：
#  A) 拿到 x-response-time-ms 且 < SLOW_SERVER_MS
#  B) 没有该响应头，但 HTTP 200（容器内本地回环常见），也视为一次 PASS
set -euo pipefail

BASE_URL="${BASE_URL:-}"
if [ -z "${BASE_URL}" ]; then
  echo "BASE_URL not set"; exit 2
fi

SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"
PASS_COUNT="${PASS_COUNT:-3}"
MAX_TRIES="${MAX_TRIES:-60}"
SLEEP_SECS="${SLEEP_SECS:-2}"

echo "⛳ Post-deploy gate @ ${BASE_URL} (server<${SLOW_SERVER_MS}ms, ${PASS_COUNT} passes)"

ok=0
try=0

while [ "${try}" -lt "${MAX_TRIES}" ]; do
  try=$((try+1))
  hdr="$(mktemp)"
  read -r code t < <(curl -sS -o /dev/null -D "$hdr" \
        -H "Accept: application/json" -w '%{http_code} %{time_total}' \
        "${BASE_URL}/v1/health" || echo "000 0")
  # 提取 header（大小写都兼容）
  server_ms="$(awk -F': ' 'tolower($1)=="x-response-time-ms"{gsub(/\r/,"",$2);print $2}' "$hdr" | head -n1)"
  rm -f "$hdr"

  e2e_ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  [ -z "${server_ms}" ] && server_ms="NA"

  echo "… try #${try} (http=${code}, e2e=${e2e_ms}ms, server=${server_ms}ms)"

  pass=0
  if [ "${code}" = "200" ]; then
    if [[ "${server_ms}" != "NA" ]]; then
      # 有服务端耗时头，按严格阈值判定
      if [ "${server_ms}" -lt "${SLOW_SERVER_MS}" ]; then pass=1; fi
    else
      # 没有该响应头（本地回环常见），只要 200 就视为通过一次
      pass=1
    fi
  fi

  if [ "${pass}" -eq 1 ]; then
    ok=$((ok+1))
    if [ "${ok}" -ge "${PASS_COUNT}" ]; then
      echo "✅ Post-deploy gate passed."
      exit 0
    fi
  else
    ok=0
  fi

  sleep "${SLEEP_SECS}"
done

echo "❌ Post-deploy gate failed."
exit 1