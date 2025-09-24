#!/usr/bin/env bash
# PortPulse PBB v1.3 统一验收脚本（线上/线下一套口径）
# 退出码：0=通过；1=前置依赖缺失；2=合同/鉴权失败；3=UNLOCODE校验失败；
#         4=ETag/HEAD/缓存失败；5=30天回放失败；6=新鲜度失败；7=错误体/alerts/sources失败；8=其他

set -euo pipefail

# --- 入参与依赖 ---
BASE="${BASE:-}"
API_KEY="${API_KEY:-}"
MODE="full"
[[ "${1:-}" == "--quick" ]] && MODE="quick"

need(){ command -v "$1" >/dev/null 2>&1 || { echo "❌ need $1"; exit 1; }; }
need curl; need jq; need awk; need sed; need date

RID(){ printf "acc-%(%Y%m%dT%H%M%S)T-%s" -1 "$RANDOM"; }
TS(){ date -u +%Y%m%dT%H%M%SZ; }

if [[ -z "${BASE}" || -z "${API_KEY}" ]]; then
  echo "❌ BASE 或 API_KEY 未设置"; exit 1
fi

# 核心 30（full）/ 抽查 3（quick）
PORTS_FULL=(USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN)
PORTS_QUICK=(USLAX NLRTM SGSIN)
PORTS=("${PORTS_FULL[@]}"); [[ "$MODE" == "quick" ]] && PORTS=("${PORTS_QUICK[@]}")

OUT="backups/$(TS)"; mkdir -p "$OUT"/{openapi,metrics,data}

echo "=== PortPulse Acceptance (PBB v1.3) ==="
echo "BASE=$BASE  PORTS=${#PORTS[@]}  MODE=$MODE"

# --- A) Health & OpenAPI 路径断言 ---
echo "[A] Health & OpenAPI..."
curl -fsS -H "x-request-id: $(RID)" "$BASE/v1/health" | jq -e '.ok==true' >/dev/null || { echo "❌ /v1/health"; exit 2; }
curl -fsSI -H "x-request-id: $(RID)" "$BASE/openapi.json" | awk -F': ' 'tolower($1)=="content-type"{print tolower($2)}' | grep -q 'application/json' || { echo "❌ openapi content-type"; exit 2; }
curl -fsS "$BASE/openapi.json" > "$OUT/openapi/openapi.json"
jq -e '
  .paths
  | has("/v1/health")
  and has("/v1/sources")
  and has("/v1/ports/{unlocode}/trend")
  and has("/v1/ports/{unlocode}/dwell")
  and has("/v1/ports/{unlocode}/snapshot")
  and has("/v1/ports/{unlocode}/alerts")
  and has("/v1/hs/{code}/imports")
' "$OUT/openapi/openapi.json" >/dev/null || { echo "❌ openapi paths"; exit 2; }
echo "✅ A OK"

# --- B) 鉴权（401/200） ---
echo "[B] Auth..."
unauth=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/ports/USLAX/trend?days=7")
[[ "$unauth" =~ ^(401|403)$ ]] || { echo "❌ unauth expected 401/403, got $unauth"; exit 2; }
auth=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE/v1/ports/USLAX/trend?days=7")
[[ "$auth" == "200" ]] || { echo "❌ auth expected 200, got $auth"; exit 2; }
echo "✅ B OK"

# --- C) UNLOCODE 校验（422/404 必须） ---
echo "[C] UNLOCODE validators..."
code422=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE/v1/ports/NO_PORT/trend?days=7")
[[ "$code422" == "422" ]] || { echo "❌ bad-format expected 422, got $code422"; exit 3; }
code404=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE/v1/ports/ZZZZZ/trend?days=7")
[[ "$code404" == "404" ]] || { echo "❌ not-exist expected 404, got $code404"; exit 3; }
echo "✅ C OK"

# --- D) JSON/CSV + ETag/304 + HEAD/Cache-Control ---
echo "[D] CSV/ETag/HEAD..."
PORT="USLAX"
JSON_URL="$BASE/v1/ports/$PORT/trend?days=7"
CSV_URL="$JSON_URL&format=csv"
curl -fsS -H "X-API-Key: $API_KEY" "$JSON_URL" | jq -e '.points|length>=1' >/dev/null || { echo "❌ trend points missing"; exit 4; }
H=$(curl -fsS -D - -H "X-API-Key: $API_KEY" "$CSV_URL" -o /dev/null)
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1} /^etag:/{gsub(/\r|\"/,"");print $2}')
[[ -n "$ET" ]] || { echo "❌ ETag missing"; exit 4; }
code304=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$ET\"" "$CSV_URL")
[[ "$code304" == "304" ]] || { echo "❌ If-None-Match not 304 ($code304)"; exit 4; }
HEADS=$(curl -fsSI -H "X-API-Key: $API_KEY" "$CSV_URL")
echo "$HEADS" > "$OUT/metrics/etag_head.txt"
echo "$H"     > "$OUT/metrics/etag_200_headers.txt"
grep -qi '^cache-control:.*public, *max-age=300.*no-transform' <<<"$HEADS" || { echo "❌ cache-control missing/incorrect"; exit 4; }
grep -qi '^content-type: *text/csv' <<<"$HEADS" || { echo "❌ content-type not csv"; exit 4; }
echo "✅ D OK"

# --- E) /v1/sources 透明度 ---
echo "[E] /v1/sources..."
curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/sources" > "$OUT/data/sources.json"
jq -e '.sources and (.sources|length>=1) and (.sources[0]|has("name") and has("last_ingest_at"))' "$OUT/data/sources.json" >/dev/null || { echo "❌ sources shape"; exit 7; }
echo "✅ E OK"

# --- F) 30天回放连续性 ---
echo "[F] 30d continuity..."
trend_txt="$OUT/metrics/trend_30d_points.txt"; : > "$trend_txt"
fail_cont=0
for p in "${PORTS[@]}"; do
  len=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$p/trend?days=30" | jq '.points|length')
  printf "%-6s points=%s\n" "$p" "$len" | tee -a "$trend_txt"
  [[ "${len:-0}" -ge 30 ]] || { echo "  -> ❌ $p continuity <30"; fail_cont=$((fail_cont+1)); }
done
[[ "$fail_cont" -eq 0 ]] || { echo "❌ continuity failed ($fail_cont)"; exit 5; }
echo "✅ F OK"

# --- G) 新鲜度 ≤2h（逐港 + p95 粗算） ---
echo "[G] freshness <=2h..."
OUT=${OUT:-backups/$(date -u +%Y%m%dT%H%M%SZ)}
bash scripts/freshness_calc.sh
