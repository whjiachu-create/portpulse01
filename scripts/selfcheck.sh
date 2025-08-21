#!/usr/bin/env bash
# scripts/selfcheck.sh (v2)
# 说明：
# - 仍按原顺序检查 7 个端点；
# - 任何端点 HTTP 非 200 或耗时 >= SLOW_MS（默认 800ms）→ 脚本以非 0 退出；
# - 方便在 CI 里作为守门 & 告警触发器。

set -u  # 避免使用未定义变量

: "${BASE_URL:?BASE_URL not set}"
: "${API_KEY:?API_KEY not set}"
SLOW_MS="${SLOW_MS:-800}"   # 可在外部覆写阈值（毫秒）

green(){ printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
red(){ printf '\033[31m%s\033[0m\n' "$*"; }

# 通用 JSON 接口测速 + 校验
# 用法：measure_json "名字" "URL" [可选：额外 curl 参数，如 -H "X-API-Key: xxx"]
measure_json() {
  local name="$1" url="$2"; shift 2 || true
  # 输出：HTTP_CODE TIME_TOTAL
  read -r code t < <(curl -sS -H "Accept: application/json" "$@" -o /dev/null \
                     -w '%{http_code} %{time_total}' "$url")
  # 秒转毫秒（整数）
  local ms; ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  if [ "$code" != "200" ]; then
    red "✗ $name  HTTP $code (${ms}ms)"
    return 2
  fi
  if [ "$ms" -ge "$SLOW_MS" ]; then
    yellow "! $name  ${ms}ms (>= ${SLOW_MS}ms)"
    return 1
  fi
  green "✓ $name  ${ms}ms"
  return 0
}

# CSV 接口测速 + 表头校验
# 用法：measure_csv "名字" "URL" '期望开头' [可选：额外 curl 参数]
measure_csv() {
  local name="$1" url="$2" expect="$3"; shift 3 || true
  local tmp; tmp="$(mktemp)"
  read -r code t < <(curl -sS "$@" -o "$tmp" -w '%{http_code} %{time_total}' "$url")
  local ms; ms=$(awk -v tt="$t" 'BEGIN{printf "%d", tt*1000}')
  if [ "$code" != "200" ]; then
    red "✗ $name  HTTP $code (${ms}ms)"
    rm -f "$tmp"
    return 2
  fi
  local head; head="$(head -n1 "$tmp" | tr -d '\r')"
  rm -f "$tmp"
  if [[ "$head" != "$expect"* ]]; then
    red "✗ $name  bad header '${head}' (${ms}ms)"
    return 2
  fi
  if [ "$ms" -ge "$SLOW_MS" ]; then
    yellow "! $name  ${ms}ms (>= ${SLOW_MS}ms)"
    return 1
  fi
  green "✓ $name  ${ms}ms"
  return 0
}

echo "🔎 Smoke @ ${BASE_URL}  (threshold=${SLOW_MS}ms)"

slow=0
fail=0

# 1) health（无鉴权）
measure_json "/v1/health" "${BASE_URL}/v1/health" || case $? in 1) slow=1;; 2) fail=1;; esac

# 2) sources（无鉴权）
measure_json "/v1/sources" "${BASE_URL}/v1/sources" || case $? in 1) slow=1;; 2) fail=1;; esac

# 3) snapshot（鉴权）
measure_json "/v1/ports/USLAX/snapshot" \
  "${BASE_URL}/v1/ports/USLAX/snapshot" -H "X-API-Key: ${API_KEY}" \
  || case $? in 1) slow=1;; 2) fail=1;; esac

# 4) dwell（鉴权）
measure_json "/v1/ports/USLAX/dwell?days=14" \
  "${BASE_URL}/v1/ports/USLAX/dwell?days=14" -H "X-API-Key: ${API_KEY}" \
  || case $? in 1) slow=1;; 2) fail=1;; esac

# 5) overview（CSV，鉴权，校验表头）
measure_csv "/v1/ports/USLAX/overview?format=csv" \
  "${BASE_URL}/v1/ports/USLAX/overview?format=csv" 'unlocode,as_of' -H "X-API-Key: ${API_KEY}" \
  || case $? in 1) slow=1;; 2) fail=1;; esac

# 6) alerts（鉴权）
measure_json "/v1/ports/USNYC/alerts?window=14d" \
  "${BASE_URL}/v1/ports/USNYC/alerts?window=14d" -H "X-API-Key: ${API_KEY}" \
  || case $? in 1) slow=1;; 2) fail=1;; esac

# 7) trend（鉴权）
measure_json "/v1/ports/USLAX/trend?days=30&fields=vessels,avg_wait_hours&limit=30&offset=0" \
  "${BASE_URL}/v1/ports/USLAX/trend?days=30&fields=vessels,avg_wait_hours&limit=30&offset=0" \
  -H "X-API-Key: ${API_KEY}" \
  || case $? in 1) slow=1;; 2) fail=1;; esac

if [ "$fail" -eq 0 ] && [ "$slow" -eq 0 ]; then
  echo "✅ All green"
  exit 0
fi

[ "$fail" -ne 0 ] && echo "❌ At least one endpoint failed (non-200 or bad payload)."
[ "$slow" -ne 0 ] && echo "⚠️  At least one endpoint is slow (>= ${SLOW_MS}ms)."
exit 1