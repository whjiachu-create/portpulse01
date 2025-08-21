#!/usr/bin/env bash
# scripts/health_gate.sh
# 用法（Railway Post-deploy）：BASE_URL=https://api.useportpulse.com bash scripts/health_gate.sh
set -euo pipefail

: "${BASE_URL:?BASE_URL not set}"
# 要求：/v1/health 200 且 x-response-time-ms < 300，连续 3 次
TRIES="${TRIES:-20}"         # 最多尝试 20 次
SLEEP="${SLEEP:-5}"          # 间隔 5s
THRESH_MS="${THRESH_MS:-300}"
PASS_IN_A_ROW="${PASS_IN_A_ROW:-3}"

echo "⛳ Post-deploy gate @ ${BASE_URL} (server<${THRESH_MS}ms, ${PASS_IN_A_ROW} passes)"

ok=0
for i in $(seq 1 "$TRIES"); do
  read -r code ms < <(curl -sSD - "${BASE_URL}/v1/health" -o /dev/null \
                       -w "%{http_code} %{time_total}" \
                       | awk 'NR==0{print} END{ }' ) || true

  # 取响应头里的 x-response-time-ms（没有就用 time_total*1000 兜底）
  hdr_ms=$(curl -sSD - "${BASE_URL}/v1/health" -o /dev/null \
           | awk -F': ' 'tolower($1)=="x-response-time-ms"{gsub(/\r/,"",$2);print $2}' | tail -n1)
  if [[ -z "$hdr_ms" ]]; then
    hdr_ms=$(awk -v t="$ms" 'BEGIN{printf "%d", t*1000}')
  fi

  if [[ "$code" == "200" && "$hdr_ms" -lt "$THRESH_MS" ]]; then
    ok=$((ok+1)); echo "✓ pass ${ok}/${PASS_IN_A_ROW}  (http=$code, server=${hdr_ms}ms)"
  else
    ok=0; echo "… wait (http=${code:-NA}, server=${hdr_ms:-NA}ms)"
  fi

  if [[ "$ok" -ge "$PASS_IN_A_ROW" ]]; then
    echo "✅ Healthy after deploy."
    exit 0
  fi
  sleep "$SLEEP"
done

echo "❌ Post-deploy gate failed."
exit 1