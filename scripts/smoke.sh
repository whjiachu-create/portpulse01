#!/usr/bin/env bash
# PortPulse / Smoke Tests (v3 CI-proof)

set -euo pipefail

: "${API_KEY:?API_KEY is required}"
BASE_URL="${BASE_URL:-https://api.useportpulse.com}"
BASE_URL="${BASE_URL%/}"

PORT_OVERVIEW="${PORT_OVERVIEW:-USLAX}"
PORT_ALERTS="${PORT_ALERTS:-USNYC}"
ALERT_WINDOW="${ALERT_WINDOW:-14d}"

UA="PortPulseSmoke/1.2"
CURL="curl -sS --http1.1 --retry 2 --retry-all-errors --connect-timeout 10 --max-time 25 -H User-Agent:$UA"

jsonv(){ python3 -c 'import sys,json;print(json.load(sys.stdin))'; }
say(){ printf "%s\n" "$*"; }

say "🔎 Smoke @ $BASE_URL  (overview=$PORT_OVERVIEW, alerts=$PORT_ALERTS, window=$ALERT_WINDOW)"

# 1) health
say "1) /v1/health"
H=$($CURL -H 'Accept: application/json' "$BASE_URL/v1/health" | python3 - <<'PY'
import sys,json; d=json.load(sys.stdin); assert d.get("ok") is True, d; print("ok")
PY
)
say "✅ health $H"

# 2) sources
say "2) /v1/meta/sources"
S=$($CURL -H "X-API-Key: $API_KEY" "$BASE_URL/v1/meta/sources" | python3 - <<'PY'
import sys,json; d=json.load(sys.stdin); assert isinstance(d,list) and len(d)>=1, d; print(len(d))
PY
)
say "✅ sources ok: $S"

# 3) overview
say "3) /v1/ports/$PORT_OVERVIEW/overview?format=json"
$CURL -H "X-API-Key: $API_KEY" "$BASE_URL/v1/ports/$PORT_OVERVIEW/overview?format=json" | python3 - <<'PY'
import sys,json; d=json.load(sys.stdin); assert "metrics" in d and "vessels" in d["metrics"], d
PY
say "✅ overview ok"

# 4) alerts
say "4) /v1/ports/$PORT_ALERTS/alerts?window=$ALERT_WINDOW"
$CURL -H "X-API-Key: $API_KEY" "$BASE_URL/v1/ports/$PORT_ALERTS/alerts?window=$ALERT_WINDOW" | python3 - <<'PY'
import sys,json; d=json.load(sys.stdin); assert "alerts" in d and isinstance(d["alerts"], list), d
PY
say "✅ alerts ok"