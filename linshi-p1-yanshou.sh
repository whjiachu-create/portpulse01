#!/usr/bin/env bash
set -euo pipefail

# ---------- Config ----------
: "${BASE:=https://api.useportpulse.com}"
: "${API_KEY:?API_KEY not set}"
: "${DEMO_KEY:=dev_demo_123}"
: "${TIMEOUT:=15}"

CORE30=(USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA \
        NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR \
        CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN)

TS_UTC="$(date -u +%Y%m%d_%H%M%S)"
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/acceptance_${TS_UTC}.log"
mkdir -p "${LOG_DIR}"

# ---------- Dependencies ----------
need() { command -v "$1" >/dev/null 2>&1 || { echo "FATAL: missing '$1'"; exit 127; }; }
need curl; need jq; need awk; need python3

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== PortPulse Acceptance @ ${TS_UTC} (UTC) ==="
echo "BASE=${BASE}"
echo "TIMEOUT=${TIMEOUT}"
echo "LOG=${LOG_FILE}"
echo

fail() { echo "FATAL: $*"; exit 1; }

section() { echo; echo "== $* =="; }

# ---------- 1. Contract & Auth ----------
section "Contract & Auth"
/usr/bin/env curl -fsS --max-time "$TIMEOUT" "${BASE}/v1/health" | jq .

# ---------- 2. OpenAPI ----------
section "OpenAPI"
/usr/bin/env curl -fsS --max-time "$TIMEOUT" "${BASE}/openapi.json" | jq -r '.openapi, .info.title, .info.version'

# ---------- 3. Unauthorized / Authorized ----------
section "Unauthorized then Authorized (USLAX trend)"
code401=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${BASE}/v1/ports/USLAX/trend?days=7")
echo "unauthorized http_code: ${code401}"
code200=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "${BASE}/v1/ports/USLAX/trend?days=7")
echo "authorized http_code:   ${code200}"

# ---------- 4. Invalid UNLOCODE should be 4xx ----------
section "Invalid UNLOCODE should be 4xx"
code_bad=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "${BASE}/v1/ports/NO_PORT/trend?days=7")
echo "invalid unlocode http_code: ${code_bad}"

# ---------- 5. CSV ETag / 304 / HEAD ----------
section "CSV ETag & 304 & HEAD"
URL="${BASE}/v1/ports/USLAX/trend?days=14&format=csv"
etag=$(curl -fsS --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" -D - "$URL" -o /dev/null | awk -F': ' 'tolower($1)=="etag"{gsub("\r","",$2); print $2}')
echo "ETag (GET #1): ${etag}"
code304=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" -H "If-None-Match: ${etag}" "$URL")
echo "GET #2 If-None-Match => ${code304} (expect 304)"
echo "HEAD headers:"
curl -fsS -I --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "$URL" | grep -iE 'HTTP/|etag|cache-control|content-type' || true

# ---------- 6. Core30 continuity ----------
section "Core30 30d continuity"
not_ok=0
for PORT in "${CORE30[@]}"; do
  n=$(curl -fsS --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" \
       "${BASE}/v1/ports/${PORT}/trend?days=30&format=json" | jq '.points|length' 2>/dev/null || echo 0)
  printf "%-6s points=%s\n" "$PORT" "$n"
  [[ "$n" == "30" ]] || { not_ok=$((not_ok+1)); echo "!! ${PORT} not 30/30"; }
done
echo "Core30 not-30/30 count: ${not_ok}"

# ---------- 7. Freshness sample ----------
section "Freshness p50/p95 (sample 4 ports)"
python3 - "$BASE" "$API_KEY" <<'PY'
import sys,os,requests,statistics,datetime as dt,json
BASE=sys.argv[1]; KEY=sys.argv[2]; ports=["USLAX","SGSIN","NLRTM","USNYC"]
def pick_ts(s):
    for k in ("last_updated","as_of","updated_at","ts"):
        if s.get(k): return s[k]
def lag_min(ts):
    t=dt.datetime.fromisoformat(ts.replace("Z","+00:00"))
    return (dt.datetime.now(dt.timezone.utc)-t).total_seconds()/60
lags=[]; per={}
for p in ports:
    js=requests.get(f"{BASE}/v1/meta/sources?port={p}",headers={"X-API-Key":KEY},timeout=15).json()
    pm=[lag_min(ts) for s in js.get("sources",[]) if (ts:=pick_ts(s))]
    if pm: pm.sort(); per[p]={"count":len(pm),"p50":statistics.median(pm),"p95":pm[int(0.95*len(pm))-1]}; lags+=pm
summary={"samples":len(lags),"overall_p50":None,"overall_p95":None,"per_port":per}
if lags: lags.sort(); summary["overall_p50"]=statistics.median(lags); summary["overall_p95"]=lags[int(0.95*len(lags))-1]
print(json.dumps(summary,indent=2))
PY

# ---------- 8. JSON/CSV parity ----------
section "JSON/CSV parity (USLAX trend 7d)"
jk=$(curl -fsS --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "${BASE}/v1/ports/USLAX/trend?days=7&format=json" \
     | jq -r '.points[0] | to_entries | map(.key) | join(",")')
ck=$(curl -fsS --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "${BASE}/v1/ports/USLAX/trend?days=7&format=csv" | head -n 1)
echo "JSON keys: ${jk}"
echo "CSV head: ${ck}"

# ---------- 9. Alerts shape ----------
section "Alerts shape (USLAX, 14d)"
curl -fsS --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" \
  "${BASE}/v1/ports/USLAX/alerts?window=14d" \
  | jq -r '{type:type, items_len: (.items|length), sample: (.items[0]|{date, severity, explain})}'

# ---------- 10. HS imports(beta) ----------
section "HS imports (beta)"
echo "OpenAPI params:"
curl -fsS --max-time "$TIMEOUT" "${BASE}/openapi.json" | jq -r '
  .paths["/v1/hs/{code}/imports"].get.parameters[]
  | [.name, .required, .schema.type, ((.schema.enum? // [])|join("|"))] | @tsv'
FROM="$(date -u -d '12 months ago' +%Y-%m || date -u -v-12m +%Y-%m)"
TO="$(date -u +%Y-%m)"
URL2="${BASE}/v1/hs/8401/imports?frm=${FROM}&to=${TO}&format=csv"
echo "Try CSV + ETag:"
curl -fsS -D - -o /dev/null --max-time "$TIMEOUT" -H "X-API-Key: ${API_KEY}" "$URL2" | sed -n '1,10p' || true

echo
echo "[DONE] Log file at: ${LOG_FILE}"