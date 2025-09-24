#!/usr/bin/env bash
set -Eeuo pipefail

# ------------- Config -------------
: "${BASE:=https://api.useportpulse.com}"   # 如需本地调试：export BASE="http://127.0.0.1:8080"
: "${TIMEOUT:=15}"
: "${API_KEY:?FATAL: API_KEY not set (export API_KEY=...)}"
: "${DEMO_KEY:=dev_demo_123}"

# Core30 白名单（用于 continuity 验证）
CORE30="USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA \
NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR \
CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN"

TS_UTC="$(date -u +'%Y%m%d_%H%M')"
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/acceptance_${TS_UTC}.log"
mkdir -p "${LOG_DIR}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "FATAL: missing '$1'"; exit 127; }; }
need curl; need jq

section() { echo; echo "== $* =="; }

{
  echo "=== PortPulse Acceptance @ ${TS_UTC} (UTC) ==="
  echo "BASE=${BASE}"
  echo "TIMEOUT=${TIMEOUT}"
  echo "LOG=${LOG_FILE}"
  echo

  # -------- 1. Contract & Auth ----------
  section "Contract & Auth"
  /usr/bin/env curl -fsS --max-time "${TIMEOUT}" "${BASE}/v1/health" | jq .

  # -------- 2. OpenAPI ----------
  section "OpenAPI"
  curl -fsS --max-time "${TIMEOUT}" "${BASE}/openapi.json" \
    | jq -r '.openapi, .info.title, .info.version, (.components.securitySchemes|keys[]? // empty)'

  # -------- 3. Unauthorized / Authorized ----------
  section "Unauthorized then Authorized (USLAX trend)"
  http_unauth=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time "${TIMEOUT}" \
      "${BASE}/v1/ports/USLAX/trend?days=7")
  http_auth=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
      "${BASE}/v1/ports/USLAX/trend?days=7")
  printf "unauthorized http_code: %s\n" "$http_unauth"
  printf "authorized http_code:   %s\n" "$http_auth"

  # -------- 4. Invalid UNLOCODE 应 4xx ----------
  section "Invalid UNLOCODE should be 4xx"
  http_bad=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
      "${BASE}/v1/ports/NO_PORT/trend?days=7")
  printf "invalid unlocode http_code: %s\n" "$http_bad"

  # -------- 5. CSV ETag & 304 & HEAD ----------
  section "CSV ETag & 304 & HEAD"
  URL="${BASE}/v1/ports/USLAX/trend?days=7&format=csv"
  etag=$(curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" -D - "$URL" -o /dev/null \
          | awk -F': ' 'tolower($1)=="etag"{gsub("\r","",$2); print $2}')
  echo "ETag (GET #1): ${etag}"
  code304=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT}" \
            -H "X-API-Key: ${API_KEY}" -H "If-None-Match: ${etag}" "$URL")
  echo "GET #2 If-None-Match => ${code304} (expect 304)"
  echo "HEAD headers:"
  curl -fsS --max-time "${TIMEOUT}" -I -H "X-API-Key: ${API_KEY}" "$URL" | sed -n '1,20p'

  # -------- 6. Core30 30d continuity ----------
  section "Core30 30d continuity"
  notok=0
  for u in $CORE30; do
    pts=$(curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
            "${BASE}/v1/ports/${u}/trend?days=30" | jq '.points|length' 2>/dev/null || echo 0)
    echo "$u  points=${pts}"
    [[ "$pts" -eq 30 ]] || notok=$((notok+1))
  done
  echo "Core30 not-30/30 count: ${notok}"

  # -------- 7. Freshness p50/p95 (sample 4 ports) ----------
  section "Freshness p50/p95 (sample 4 ports)"
  # 把关键环境导出到 Python
  export BASE API_KEY
  python3 - <<'PY'
import os,requests,statistics,datetime as dt, json
BASE=os.environ["BASE"]; KEY=os.environ["API_KEY"]
ports=["USLAX","SGSIN","NLRTM","USNYC"]
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
    if pm:
        pm.sort()
        per[p]={"count":len(pm),"p50":statistics.median(pm),"p95":pm[int(0.95*len(pm))-1]}
        lags+=pm
summary={"samples":len(lags),"overall_p50":None,"overall_p95":None,"per_port":per}
if lags:
    lags.sort()
    summary["overall_p50"]=statistics.median(lags)
    summary["overall_p95"]=lags[int(0.95*len(lags))-1]
print(json.dumps(summary,indent=2))
PY

  # -------- 8. JSON/CSV parity ----------
  section "JSON/CSV parity (USLAX trend 7d)"
  jq -r '[.[0]|keys] | @tsv' <(curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
      "${BASE}/v1/ports/USLAX/trend?days=7") \
    | sed 's/\t/,/g' | sed 's/^/JSON keys: /'
  curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
      "${BASE}/v1/ports/USLAX/trend?days=7&format=csv" | head -n 1 | sed 's/^/CSV head: /'

  # -------- 9. Alerts shape ----------
  section "Alerts shape (USLAX, 14d)"
  curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" \
    "${BASE}/v1/ports/USLAX/alerts?window=14d" \
    | jq '{type:type, items_len:(.items|length), sample:(.items[0]//null)}'

  # -------- 10. HS imports (beta) ----------
  section "HS imports (beta)"
  echo "OpenAPI params:"
  curl -fsS --max-time "${TIMEOUT}" "${BASE}/openapi.json" \
    | jq -r '.paths["/v1/hs/{code}/imports"].get.parameters[]
      | [.name, .required, .schema.type, (.schema.enum? // [] | join("|"))] | @tsv'
  FROM=$(date -u -d '12 months ago' +%Y-%m)
  TO=$(date -u +%Y-%m)
  HS_URL="${BASE}/v1/hs/8401/imports?frm=${FROM}&to=${TO}&format=csv"
  echo "Try CSV + ETag:"
  etag=$(curl -fsS --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" -D - "$HS_URL" -o /dev/null \
          | awk -F': ' 'tolower($1)=="etag"{gsub("\r","",$2); print $2}') || true
  [[ -n "${etag:-}" ]] || curl -fsS -i --max-time "${TIMEOUT}" -H "X-API-Key: ${API_KEY}" "$HS_URL" | sed -n '1,12p'
} | tee -a "${LOG_FILE}"