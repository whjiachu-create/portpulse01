#!/usr/bin/env bash
set -euo pipefail

# ======== 基本配置（从环境变量读，便于本地与CI共用） ========
BASE_URL="${BASE_URL:-https://portpulse01-production.up.railway.app}"
API_KEY="${API_KEY:?API_KEY is required (set env var or GitHub Secret)}"

echo "🔎 Smoke against: $BASE_URL"

tmpdir="$(mktemp -d)"; trap 'rm -rf "$tmpdir"' EXIT

# 小工具：保存响应、状态码、响应头
curl_save() {  # $1=URL  $2=outfile  [--no-auth]
  local url="$1"; shift
  local outfile="$1"; shift
  local headers="$outfile.headers"
  local code

  if [[ "${1:-}" == "--no-auth" ]]; then
    code=$(curl -sS -D "$headers" -o "$outfile" -w "%{http_code}" "$url")
  else
    code=$(curl -sS -H "X-API-Key: $API_KEY" -D "$headers" -o "$outfile" -w "%{http_code}" "$url")
  fi
  echo "$code"
}

must_code() {  # $1=actual $2=expected
  if [[ "$1" != "$2" ]]; then
    echo "❌ HTTP $1 (expect $2)"
    exit 1
  fi
}

must_header_contains() {  # $1=headers-file  $2=needle (case-insensitive)
  grep -iq "$2" "$1" || { echo "❌ header missing: $2"; exit 1; }
}

must_jq() {  # $1=file $2=jq-expression that returns true
  jq -e "$2" "$1" >/dev/null || { echo "❌ jq assert failed: $2"; exit 1; }
}

# -------- 1) Health --------
echo "1) /v1/health ..."
code=$(curl_save "$BASE_URL/v1/health" "$tmpdir/health.json" --no-auth)
must_code "$code" 200
must_jq "$tmpdir/health.json" '.ok == true'
echo "✅ health ok"

# -------- 2) Sources --------
echo "2) /v1/meta/sources ..."
code=$(curl_save "$BASE_URL/v1/meta/sources" "$tmpdir/sources.json")
must_code "$code" 200
must_jq "$tmpdir/sources.json" 'type=="array" and length>=1'
echo "✅ sources ok"

# -------- 3) Overview(JSON) --------
echo "3) /v1/ports/USLAX/overview (JSON) ..."
code=$(curl_save "$BASE_URL/v1/ports/USLAX/overview" "$tmpdir/overview.json")
must_code "$code" 200
must_jq "$tmpdir/overview.json" '.unlocode=="USLAX" and .metrics.vessels>=0 and .metrics.avg_wait_hours>=0 and .metrics.congestion_score>=0 and .source.src!=null and .as_of!=null'
echo "✅ overview json ok"

# -------- 4) Overview(CSV) --------
echo "4) /v1/ports/USLAX/overview?format=csv ..."
code=$(curl_save "$BASE_URL/v1/ports/USLAX/overview?format=csv" "$tmpdir/overview.csv")
must_code "$code" 200
must_header_contains "$tmpdir/overview.csv.headers" "content-type: text/csv"
head -n 1 "$tmpdir/overview.csv" | grep -qi "unlocode" || { echo "❌ csv header invalid"; exit 1; }
head -n 2 "$tmpdir/overview.csv" | tail -n 1 | grep -q "^USLAX," || { echo "❌ csv row invalid"; exit 1; }
echo "✅ overview csv ok"

# -------- 5) Alerts(JSON) --------
echo "5) /v1/ports/USNYC/alerts?window=14d ..."
code=$(curl_save "$BASE_URL/v1/ports/USNYC/alerts?window=14d" "$tmpdir/alerts.json")
must_code "$code" 200
must_jq "$tmpdir/alerts.json" 'has("alerts") and (.alerts|type=="array")'
echo "✅ alerts ok"

# -------- 6) Negative: no auth --------
echo "6) Negative: /v1/ports/USLAX/overview without API key ..."
code=$(curl_save "$BASE_URL/v1/ports/USLAX/overview" "$tmpdir/noauth.json" --no-auth)
([[ "$code" == "401" || "$code" == "403" ]]) || { echo "❌ expect 401/403, got $code"; exit 1; }
echo "✅ auth guard ok"

echo "🎉 ALL SMOKE TESTS PASSED"