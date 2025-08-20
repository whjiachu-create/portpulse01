#!/usr/bin/env bash
# PortPulse / Smoke Tests (v1.3 CI-stable)

set -euo pipefail

: "${API_KEY:?API_KEY is required (env)}"
BASE_URL="${BASE_URL:-https://api.useportpulse.com}"
BASE_URL="${BASE_URL%/}"
PORT_OVERVIEW="${PORT_OVERVIEW:-USLAX}"
PORT_ALERTS="${PORT_ALERTS:-USNYC}"
ALERT_WINDOW="${ALERT_WINDOW:-14d}"

UA="PortPulseSmoke/1.2"
CURL_OPTS="${CURL_OPTS:---http1.1}"
curlj() { # curl + 默认头
  curl -sS ${CURL_OPTS} -H "Accept: application/json" -H "User-Agent: ${UA}" "$@"
}

echo "🔎 Smoke @ ${BASE_URL}  (overview=${PORT_OVERVIEW}, alerts=${PORT_ALERTS}, window=${ALERT_WINDOW})"

# 1) /v1/health
echo "1) /v1/health"
raw="$(curlj "${BASE_URL}/v1/health" || true)"
[ -n "$raw" ] || { echo "❌ empty health body"; exit 1; }
echo "$raw" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get("ok") is True, d; print("✅ health ok")'

# 2) /v1/meta/sources
echo "2) /v1/meta/sources"
raw="$(curlj -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/meta/sources" || true)"
echo "$raw" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert isinstance(d,list) and len(d)>=1, d; print(f"✅ sources ok: {len(d)}")'

# 3) /v1/ports/<overview>/overview
echo "3) /v1/ports/${PORT_OVERVIEW}/overview?format=json"
raw="$(curlj -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview" || true)"
UNLOC="${PORT_OVERVIEW}" \
python3 -c 'import os,sys,json; d=json.load(sys.stdin); assert d.get("unlocode")==os.environ["UNLOC"], d; print("✅ overview ok")' <<<"$raw"

# 4) /v1/ports/<alerts>/alerts?window=...
echo "4) /v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}"
raw="$(curlj -H "X-API-Key: ${API_KEY}" "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}" || true)"
UNLOC="${PORT_ALERTS}" \
python3 -c 'import os,sys,json; d=json.load(sys.stdin); assert d.get("unlocode")==os.environ["UNLOC"] and isinstance(d.get("alerts"),list), d; print(f"✅ alerts ok: {len(d['alerts'])}")' <<<"$raw"

echo "🎉 ALL SMOKE TESTS PASSED"
