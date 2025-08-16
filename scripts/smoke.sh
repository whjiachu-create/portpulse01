#!/usr/bin/env bash
set -euo pipefail
PYTHON="${PYTHON:-$(which python3)}"
CURL="${CURL:-curl -sS --fail-with-body}"

echo "🔎 Smoke @ ${BASE_URL:-<unset>}  (overview=${PORT_OVERVIEW:-USLAX}, alerts=${PORT_ALERTS:-USNYC}, window=${ALERT_WINDOW:-14d})"

# 1) health
echo "1) /v1/health"
$CURL "${BASE_URL}/v1/health" \
| "$PYTHON" - <<'PY' || { echo "❌ health JSON invalid"; exit 1; }
import sys,json; d=json.load(sys.stdin); assert d.get("ok") is True
print("✅ health ok")
PY

# 2) sources
echo "2) /v1/meta/sources"
$CURL "${BASE_URL}/v1/meta/sources" \
| "$PYTHON" - <<'PY' || { echo "❌ sources invalid"; exit 1; }
import sys,json; d=json.load(sys.stdin); assert isinstance(d,list) and len(d)>=1
print("✅ sources ok")
PY

# 3) overview JSON
echo "3) /v1/ports/${PORT_OVERVIEW}/overview (JSON)"
$CURL -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview" \
| "$PYTHON" - <<'PY' || { echo "❌ overview JSON assertion failed,"; exit 1; }
import sys, json, datetime as dt, os
d=json.load(sys.stdin)
assert set(d["metrics"]).issuperset({"vessels","avg_wait_hours","congestion_score"})
asof=dt.datetime.fromisoformat(d["as_of"])
age=(dt.datetime.now(dt.timezone.utc)-asof).total_seconds()/3600
assert age <= float(os.environ.get("FRESHNESS_HOURS","48"))
print("✅ overview json ok")
PY

# 4) overview CSV
echo "4) /v1/ports/${PORT_OVERVIEW}/overview?format=csv"
CSV="$($CURL -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview?format=csv")"
echo "$CSV" | head -n1 | grep -q '^unlocode,as_of,vessels,avg_wait_hours,congestion_score$' \
  && echo "$CSV" | grep -q ",${PORT_OVERVIEW}," \
  && echo "✅ overview csv ok" \
  || { echo "❌ csv header invalid"; exit 1; }

# 5) alerts
echo "5) /v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}"
$CURL -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}" \
| "$PYTHON" - <<'PY' || { echo "❌ alerts JSON invalid"; exit 1; }
import sys,json,os; d=json.load(sys.stdin); a=d.get("alerts",[])
mn=int(os.environ.get("ALERT_MIN_COUNT","0")); mx=int(os.environ.get("ALERT_MAX_COUNT","30"))
assert mn <= len(a) <= mx
print("✅ alerts ok")
PY

# 6) 未带 Key 应 401/403
echo "6) Negative: no API key"
code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}")
if [[ "$code" == "401" || "$code" == "403" ]]; then
  echo "✅ auth guard ok"
else
  echo "❌ expect 401/403, got $code"; exit 1
fi

echo "🎉 ALL SMOKE TESTS PASSED"
