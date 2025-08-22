#!/usr/bin/env bash
# scripts/health_gate.sh (simple warmup; tolerant to missing headers)
set -euo pipefail

BASE_URL="${BASE_URL:-}"
[ -z "$BASE_URL" ] && { echo "BASE_URL not set"; exit 2; }

SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # 仅用于打印提示
PASS_COUNT="${PASS_COUNT:-1}"             # 需要连续通过的次数（默认 1 次即可）
MAX_TRIES="${MAX_TRIES:-30}"              # 最多尝试次数
SLEEP_SECS="${SLEEP_SECS:-2}"

echo "⛳ Post-deploy gate @ ${BASE_URL} (server<${SLOW_SERVER_MS}ms, ${PASS_COUNT} pass)"

ok=0
for ((i=1; i<=MAX_TRIES; i++)); do
  hdr="$(mktemp)"
  # 取 HTTP 码与总耗时（秒）
  read -r code t < <(curl -sS -o /dev/null -D "$hdr" -H "Accept: application/json" \
                      -w '%{http_code} %{time_total}' "${BASE_URL}/v1/health" || echo "000 0")
  # 抽取 x-response-time-ms（可能没有）
  server_ms="$(awk -F': ' 'tolower($1)=="x-response-time-ms"{gsub(/\r/,"",$2);print $2}' "$hdr" | head -n1)"
  rm -f "$hdr"
  e2e_ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  [ -z "$server_ms" ] && server_ms="NA"

  echo "… try #${i} (http=${code}, e2e=${e2e_ms}ms, server=${server_ms}ms)"

  if [ "$code" = "200" ]; then
    ok=$((ok+1))
    if [ "$ok" -ge "$PASS_COUNT" ]; then
      echo "✅ Post-deploy gate passed."
      exit 0
    fi
  else
    ok=0
  fi
  sleep "$SLEEP_SECS"
done

echo "❌ Post-deploy gate failed (no consecutive 200)."
exit 1