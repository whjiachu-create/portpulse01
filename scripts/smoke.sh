#!/usr/bin/env bash
# PortPulse / Smoke Tests (v2.1 hardened)

set -euo pipefail

: "${API_KEY:?API_KEY is required (env)}"
BASE_URL="${BASE_URL:-https://api.useportpulse.com}"
BASE_URL="${BASE_URL%/}"

PORT_OVERVIEW="${PORT_OVERVIEW:-USLAX}"
PORT_ALERTS="${PORT_ALERTS:-USNYC}"
ALERT_WINDOW="${ALERT_WINDOW:-14d}"

MAX_VESSELS="${MAX_VESSELS:-500}"
MAX_WAIT_HOURS="${MAX_WAIT_HOURS:-24}"
MAX_CONGESTION="${MAX_CONGESTION:-100}"
FRESHNESS_HOURS="${FRESHNESS_HOURS:-48}"

UA="PortPulseSmoke/1.1"

function jassert() { python3 - "$@" <<'PY'
import sys, json, os
data = json.load(sys.stdin)
code = compile(os.environ["EXPR"], "<expr>", "eval")
ok = eval(code, {"data": data})
assert ok, os.environ.get("MSG","assert failed")
PY
}

echo "🔎 Smoke @ ${BASE_URL}  (overview=${PORT_OVERVIEW}, alerts=${PORT_ALERTS}, window=${ALERT_WINDOW})"

# 1) health
echo "1) /v1/health"
curl -sS -H "Accept: application/json" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/health" \
| EXPR='data.get("ok") is True' MSG='health not ok' jassert
echo "✅ health ok"

# 2) meta/sources（无参）
echo "2) /v1/meta/sources"
curl -sS -H "X-API-Key: ${API_KEY}" -H "Accept: application/json" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/meta/sources" \
| EXPR='"sources" in data and isinstance(data["sources"], list)' MSG='sources invalid' jassert
echo "✅ sources ok"

# 3) overview JSON
echo "3) /v1/ports/${PORT_OVERVIEW}/overview (JSON)"
OV_J="$(curl -sS -H "X-API-Key: ${API_KEY}" -H "Accept: application/json" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview")"
echo "$OV_J" \
| EXPR='data["unlocode"] and data["metrics"]["vessels"]>=0' MSG='overview json invalid' jassert
# 新鲜度校验
python3 - <<'PY'
import sys, json, os, datetime as dt
d=json.loads(open(0).read())
asof=dt.datetime.fromisoformat(d["as_of"])
age=(dt.datetime.now(dt.timezone.utc) - asof).total_seconds()/3600
assert age <= float(os.environ["FRESHNESS_HOURS"]), f"too old: {age}h"
PY
echo "✅ overview json ok"

# 4) overview CSV
echo "4) /v1/ports/${PORT_OVERVIEW}/overview?format=csv"
OV_CSV="$(curl -sS -H "X-API-Key: ${API_KEY}" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview?format=csv")"
echo "$OV_CSV" | head -n 1 | grep -q "^unlocode,as_of,vessels,avg_wait_hours,congestion_score$"
echo "✅ overview csv ok"

# 5) alerts
echo "5) /v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}"
curl -sS -H "X-API-Key: ${API_KEY}" -H "Accept: application/json" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}" \
| EXPR='"alerts" in data and "window_days" in data' MSG='alerts invalid' jassert
echo "✅ alerts ok"

# 6) Negative: no API key
echo "6) Negative: no API key"
CODE="$(curl -sS -o /dev/null -w '%{http_code}' -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview")"
if [[ "$CODE" == "401" || "$CODE" == "403" ]]; then
  echo "✅ auth guard ok"
else
  echo "❌ expect 401/403, got ${CODE}"
  exit 1
fi

# 7) trend（新增：fields + limit/offset + csv）
echo "7) /v1/ports/${PORT_OVERVIEW}/trend?days=90&fields=vessels,avg_wait_hours&format=csv&limit=10&offset=0"
TR_CSV="$(curl -sS -H "X-API-Key: ${API_KEY}" -H "User-Agent: ${UA}" \
  "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/trend?days=90&fields=vessels,avg_wait_hours&format=csv&limit=10&offset=0")"
echo "$TR_CSV" | head -n1 | grep -q "^date,vessels,avg_wait_hours$"
ROWS="$(printf "%s" "$TR_CSV" | wc -l | tr -d ' ')"
if [[ "$ROWS" -ge 2 ]]; then
  echo "✅ trend csv ok"
else
  echo "❌ trend csv empty"; exit 1
fi

echo "🎉 ALL SMOKE TESTS PASSED"