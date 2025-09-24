#!/usr/bin/env bash
set -euo pipefail
trap 'code=$?; echo "[ERR] exit $code at line $LINENO"; exit $code' ERR

: "${BASE:=https://api.useportpulse.com}"
: "${API_KEY:?FATAL: API_KEY not set}"

RID(){ printf "reg-%(%Y%m%dT%H%M%S)T-%s" -1 "$RANDOM"; }
NOW_UTC=$(date -u +%s)
FRESH_THRESH_SEC=$((2*3600))

PORTS=(USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN)

# Robust: accept YYYY-MM-DD or ISO timestamps; return "" on failure
dt_to_epoch(){ python3 - <<'PY'
import sys, datetime as dt
s=sys.stdin.read().strip()
try:
    if not s:
        print(""); sys.exit(0)
    if "T" in s:
        z = s.endswith("Z")
        if z: s = s[:-1]
        t = dt.datetime.fromisoformat(s)
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        print(int(t.timestamp()))
    else:
        y,m,d = map(int, s.split("-"))
        print(int(dt.datetime(y,m,d,tzinfo=dt.timezone.utc).timestamp()))
except Exception:
    print("")
PY
}

ok_ports=0; total=${#PORTS[@]}
cont_bad=0; fresh_bad=0; fatal_ports=0

for p in "${PORTS[@]}"; do
  echo "== $p"
  url="$BASE/v1/ports/$p/trend?days=30"
  out="/tmp/pp_${p}_trend.json"
  code=$(curl -s -o "$out" -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$url" || true)
  if [[ "$code" != "200" ]]; then
    echo "❌ http_code=$code while fetching $url"
    head -c 400 "$out" 2>/dev/null; echo
    ((fatal_ports++))
    continue
  fi

  json=$(cat "$out")
  len=$(jq '.points|length' <<<"$json")
  last_date=$(jq -r '.points|sort_by(.date)|last.date // empty' <<<"$json")

  if [[ "$len" -lt 30 ]]; then
    echo "❌ continuity <30 days (len=$len)"
    ((cont_bad++))
  fi

  if [[ -z "$last_date" ]]; then
    echo "❌ no last date"
    ((fresh_bad++))
    delta=$((FRESH_THRESH_SEC+1))
  else
    last_ts=$(printf "%s" "$last_date" | dt_to_epoch)
    if [[ -z "$last_ts" ]]; then
      echo "❌ invalid last date: $last_date"
      ((fresh_bad++))
      delta=$((FRESH_THRESH_SEC+1))
    else
      delta=$(( NOW_UTC - last_ts ))
      if (( delta > FRESH_THRESH_SEC )); then
        echo "❌ freshness > 2h (delta=${delta}s)"
        ((fresh_bad++))
      else
        echo "✅ freshness OK (delta=${delta}s)"
      fi
    fi
  fi

  if [[ "$len" -ge 30 && "$delta" -le "$FRESH_THRESH_SEC" ]]; then
    ((ok_ports++))
  fi
done

echo "---- Summary ----"
echo "Ports OK: $ok_ports/$total"
echo "Continuity bad: $cont_bad"
echo "Freshness bad: $fresh_bad"
echo "HTTP non-200 ports: $fatal_ports"

if (( cont_bad==0 && fresh_bad==0 && fatal_ports==0 )); then
  echo "✅ P1 data quality gate PASSED"; exit 0
else
  echo "❌ P1 data quality gate FAILED"; exit 2
fi
