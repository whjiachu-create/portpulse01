#!/usr/bin/env bash
# PortPulse Smoke v3 - robust & CI-safe

set -Eeuo pipefail

: "${API_KEY:?API_KEY required}"
BASE_URL="${BASE_URL:-https://api.useportpulse.com}"
BASE_URL="${BASE_URL%/}"
PORT_OVERVIEW="${PORT_OVERVIEW:-USLAX}"
PORT_ALERTS="${PORT_ALERTS:-USNYC}"
ALERT_WINDOW="${ALERT_WINDOW:-14d}"
UA="PortPulseSmoke/1.3"

curl_json() { # url
  curl -sS --http1.1 \
    --retry 3 --retry-all-errors --max-time 20 \
    -H "Accept: application/json" \
    -H "User-Agent: ${UA}" \
    -H "X-API-Key: ${API_KEY}" \
    "$1"
}

echo "🔎 Smoke @ ${BASE_URL}  (overview=${PORT_OVERVIEW}, alerts=${PORT_ALERTS}, window=${ALERT_WINDOW})"

# 1) health
echo "1) /v1/health"
RESP="$(curl -sS --http1.1 --retry 3 --retry-all-errors --max-time 15 \
  -H 'Accept: application/json' -H "User-Agent: ${UA}" "${BASE_URL}/v1/health")" || true
RESP="${RESP:-}"
RESP="$RESP" python3 -c 'import os,json,sys
b=os.environ["RESP"].strip()
assert b, "empty body from /v1/health"
d=json.loads(b)
assert d.get("ok") is True, f"health not ok: {d}"
print("✅ health ok")'

# 2) sources
echo "2) /v1/meta/sources"
RESP="$(curl_json "${BASE_URL}/v1/meta/sources")" || true
RESP="${RESP:-}"
RESP="$RESP" python3 -c 'import os,json
b=os.environ["RESP"].strip()
assert b, "empty body from /v1/meta/sources"
d=json.loads(b)
assert isinstance(d,list) and len(d)>=1, f"sources invalid: {d}"
print(f"✅ sources ok: {len(d)}")'

# 3) overview (force json to避开CSV边界)
echo "3) /v1/ports/${PORT_OVERVIEW}/overview?format=json"
RESP="$(curl_json "${BASE_URL}/v1/ports/${PORT_OVERVIEW}/overview?format=json")" || true
RESP="${RESP:-}"
RESP="$RESP" python3 -c 'import os,json
b=os.environ["RESP"].strip()
assert b, "empty body from /overview"
d=json.loads(b)
assert d.get("unlocode") and d.get("metrics"), f"overview invalid: {d}"
print("✅ overview ok")'

# 4) alerts
echo "4) /v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}"
RESP="$(curl_json "${BASE_URL}/v1/ports/${PORT_ALERTS}/alerts?window=${ALERT_WINDOW}")" || true
RESP="${RESP:-}"
RESP="$RESP" python3 -c 'import os,json
b=os.environ["RESP"].strip()
assert b, "empty body from /alerts"
d=json.loads(b)
al=d.get("alerts",[])
assert isinstance(al,list), f"alerts invalid shape: {d}"
print(f"✅ alerts ok: {len(al)}")'