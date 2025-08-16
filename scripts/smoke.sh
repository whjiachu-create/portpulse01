#!/usr/bin/env bash
set -euo pipefail

# 环境变量（本地/CI均可用）
: "${BASE_URL:?BASE_URL is required}"
: "${API_KEY:?API_KEY is required}"

PYTHON=${PYTHON:-python3}

PORT_OVERVIEW="${PORT_OVERVIEW:-USLAX}"
PORT_ALERTS="${PORT_ALERTS:-USNYC}"
ALERT_WINDOW="${ALERT_WINDOW:-14d}"
FRESHNESS_HOURS="${FRESHNESS_HOURS:-48}"

MAX_VESSELS="${MAX_VESSELS:-400}"
MAX_WAIT_HOURS="${MAX_WAIT_HOURS:-12}"
MAX_CONGESTION="${MAX_CONGESTION:-80}"

ALERT_MIN_COUNT="${ALERT_MIN_COUNT:-0}"
ALERT_MAX_COUNT="${ALERT_MAX_COUNT:-30}"

echo "🔎 Smoke @ ${BASE_URL}  (overview=${PORT_OVERVIEW}, alerts=${PORT_ALERTS}, window=${ALERT_WINDOW})"

fail(){ echo "❌ $*"; exit 1; }
ok(){ echo "✅ $*"; }

# 1) health
echo "1) /v1/health"
curl -s "${BASE_URL}/v1/health" | python3 - <<'PY' || fail "health JSON invalid"
import sys, json
d=json.load(sys.stdin)
assert d.get("ok") is True
PY
ok "health ok"

# 2) sources
echo "2) /v1/meta/sources"
curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/meta/sources" | "$PYTHON" - <<'PY' || fail "sources JSON invalid"
import sys, json
d=json.load(sys.stdin)
assert isinstance(d, list) and len(d)>=1
PY
ok "sources ok"

# 3) overview json
echo "3) /v1/ports/${PORT_OVERVIEW}/overview (JSON)"
OV_JSON="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview")"
echo "${OV_JSON}" | "$PYTHON" - <<PY || fail "overview JSON assertion failed,"
import sys, json, datetime
d=json.load(sys.stdin)
as_of=d["as_of"]
m=d["metrics"]
t=datetime.datetime.fromisoformat(as_of)
age=(datetime.datetime.now(datetime.timezone.utc)-t).total_seconds()/3600
assert age <= float("${FRESHNESS_HOURS}")
assert 0 <= m["vessels"] <= float("${MAX_VESSELS}")
assert 0.0 <= m["avg_wait_hours"] <= float("${MAX_WAIT_HOURS}")
assert 0.0 <= m["congestion_score"] <= float("${MAX_CONGESTION}")
PY
ok "overview json ok"

# 4) overview csv
echo "4) /v1/ports/${PORT_OVERVIEW}/overview?format=csv"
OV_CSV="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview?format=csv")"
echo "${OV_CSV}" | "$PYTHON" - <<'PY' || fail "csv header invalid"
import sys
s=sys.stdin.read().strip()
# 只有数据行（本接口不返回 header），校验列数=5
cols=len(s.split(","))
assert cols==5
PY
ok "overview csv ok"

# 5) trend json
echo "5) /v1/ports/${PORT_OVERVIEW}/trend?days=14 (JSON)"
TR_JSON="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/trend?days=14")"
echo "${TR_JSON}" | "$PYTHON" - <<'PY' || fail "trend JSON invalid"
import sys, json
d=json.load(sys.stdin)
pts=d.get("points", [])
assert isinstance(pts, list) and len(pts)>=3
p=pts[-1]
assert {"date","vessels","avg_wait_hours","congestion_score","src"} <= p.keys()
PY
ok "trend json ok"

# 6) trend csv
echo "6) /v1/ports/${PORT_OVERVIEW}/trend?days=14&format=csv"
TR_CSV="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/trend?days=14&format=csv")"
echo "${TR_CSV}" | head -n1 | grep -q "^date,vessels,avg_wait_hours,congestion_score,src$" || fail "trend csv header invalid"
ok "trend csv ok"

# 7) alerts
echo "7) /v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}"
AL_JSON="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}")"
echo "${AL_JSON}" | python3 - <<PY || fail "alerts JSON invalid"
import sys, json
d=json.load(sys.stdin)
cnt=len(d.get("alerts", []))
assert int("${ALERT_MIN_COUNT}") <= cnt <= int("${ALERT_MAX_COUNT}")
PY
ok "alerts ok"

# 8) negative: no api key
echo "8) Negative: no API key"
HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}")"
if [[ "${HTTP_CODE}" == "401" || "${HTTP_CODE}" == "403" ]]; then
  ok "auth guard ok"
else
  fail "expect 401/403, got ${HTTP_CODE}"
fi

echo "🎉 ALL SMOKE TESTS PASSED"