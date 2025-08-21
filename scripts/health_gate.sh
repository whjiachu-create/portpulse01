#!/usr/bin/env bash
# scripts/health_gate.sh (hardened)
# 规则：连续 PASS_COUNT 次满足 (HTTP 200 且 x-response-time-ms < 阈值) 即视为通过
# 用于 Railway Post-Deploy 或本地验证

set -euo pipefail

BASE_URL="${BASE_URL:-}"
if [ -z "${BASE_URL}" ]; then
  echo "BASE_URL not set"; exit 2
fi

SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # 服务端阈值（x-response-time-ms）
PASS_COUNT="${PASS_COUNT:-3}"             # 需要连续通过的次数
MAX_TRIES="${MAX_TRIES:-60}"              # 最多尝试次数（每次间隔 2s）
SLEEP_SECS="${SLEEP_SECS:-2}"

echo "⛳ Post-deploy gate @ ${BASE_URL} (server<${SLOW_SERVER_MS}ms, ${PASS_COUNT} passes)"

ok=0
try=0

while [ "$try" -lt "$MAX_TRIES" ]; do
  try=$((try+1))
  # 抓 HTTP 码与总耗时，并把响应头另存
  hdr="$(mktemp)"
  read -r code t < <(curl -sS -o /dev/null -D "$hdr" \
        -H "Accept: application/json" -w '%{http_code} %{time_total}' \
        "${BASE_URL}/v1/health" || echo "000 0")
  # 解析 x-response-time-ms（可能不存在）
  server_ms="$(awk -F': ' 'tolower($1)=="x-response-time-ms"{gsub(/\r/,"",$2);print $2}' "$hdr" | head -n1)"
  rm -f "$hdr"

  # 统一成整数毫秒
  e2e_ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  if [[ -z "$server_ms" ]]; then server_ms="NA"; fi

  # 打印每次尝试结果
  echo "… try #$try (http=${code}, e2e=${e2e_ms}ms, server=${server_ms}ms)"

  # 判定
  if [ "$code" = "200" ] && [[ "$server_ms" != "NA" ]] && [ "$server_ms" -lt "$SLOW_SERVER_MS" ]; then
    ok=$((ok+1))
    if [ "$ok" -ge "$PASS_COUNT" ]; then
      echo "✅ Post-deploy gate passed."
      exit 0
    fi
  else
    ok=0  # 连续通过被打断
  fi

  sleep "$SLEEP_SECS"
done

echo "❌ Post-deploy gate failed."
exit 1
