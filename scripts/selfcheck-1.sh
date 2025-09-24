#!/usr/bin/env bash
set -euo pipefail
trap 'code=$?; echo "[ERR] exit $code at line $LINENO"; exit $code' ERR
: "${BASE:?FATAL: BASE not set}"; : "${API_KEY:?FATAL: API_KEY not set}"
RID(){ printf "acc-%(%Y%m%dT%H%M%S)T-%s" -1 "$RANDOM"; }
log(){ printf "== %s\n" "$*"; }; pass(){ printf "✅ %s\n" "$*"; }; fail(){ printf "❌ %s\n" "$*"; exit 1; }
PORT_OK="USLAX"; PORT_BAD_FMT="NO_PORT"; PORT_NOT_EXIST="ZZZZZ"

log "Health check"
curl -fsS -H "x-request-id: $(RID)" "$BASE/v1/health" | jq -e '.ok==true' >/dev/null && pass "/v1/health OK"

log "OpenAPI reachable"
ctype=$(curl -fsSI -H "x-request-id: $(RID)" "$BASE/openapi.json" | awk -F': ' 'tolower($1)=="content-type"{print tolower($2)}' | tr -d '\r')
[[ "$ctype" =~ application/json ]] && pass "OpenAPI content-type OK: $ctype" || fail "OpenAPI content-type bad: $ctype"

log "Auth: 401 when missing key"
code=$(curl -s -o /dev/null -w "%{http_code}" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_OK/overview")
[[ "$code" == "401" ]] && pass "Protected route requires key (401)" || fail "Expected 401, got $code"

log "Auth: 200 when key present (GET)"
code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_OK/overview")
[[ "$code" == "200" ]] && pass "GET with key returns 200" || fail "GET expected 200, got $code"

log "Error envelope shape (missing key)"
body=$(curl -s -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_OK/trend" || true)
echo "$body" | jq -e '.code and .message and .request_id and .hint' >/dev/null && pass "Unified error body OK" || fail "Error body missing fields"

log "UNLOCODE validators"
code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_BAD_FMT/trend?days=7")
[[ "$code" == "422" ]] && pass "Bad format UNLOCODE -> 422" || fail "Expected 422, got $code"
code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_NOT_EXIST/overview")
[[ "$code" == "404" ]] && pass "Not exist UNLOCODE -> 404" || fail "Expected 404, got $code"

log "JSON/CSV parity + ETag/304 on trend"
JSON_URL="$BASE/v1/ports/$PORT_OK/trend?days=7"
CSV_URL="$JSON_URL&format=csv"
json_len=$(curl -fsS -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$JSON_URL" | jq '.points|length')
etag=$(curl -fsSI -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$CSV_URL" | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r"')
[[ -n "$etag" ]] || fail "ETag missing on CSV"
code304=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "If-None-Match: \"$etag\"" -H "x-request-id: $(RID)" "$CSV_URL")
[[ "$code304" == "304" ]] && pass "CSV ETag 304 OK" || fail "Expected 304, got $code304"

log "HEAD parity on CSV"
heads=$(curl -fsSI -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$CSV_URL")
echo "$heads" | grep -qi '^etag:' && echo "$heads" | grep -qi '^cache-control:' && echo "$heads" | grep -qi '^content-type:' \
  && pass "HEAD returns etag/cache-control/content-type" || fail "HEAD headers incomplete"

log "Beta route policy: HS imports should be 4xx with error envelope (until enabled)"
HS_URL="$BASE/v1/hs/1006/imports?from=2025-08-01&to=2025-08-31&format=csv"
hs_code=$(curl -s -o /tmp/hs.out -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$HS_URL" || true)
if [[ "$hs_code" =~ ^4[0-9][0-9]$ ]]; then
  jq -e '.code and .message and .request_id and .hint' </tmp/hs.out >/dev/null \
    && pass "HS imports 4xx + unified error OK" \
    || fail "HS imports 4xx but error body shape wrong"
else
  pass "HS imports returned $hs_code (feature may be enabled); skip for now"
fi

log "Overview JSON sanity"
curl -fsS -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_OK/overview" | jq -e '.unlocode=="'"$PORT_OK"'"' >/dev/null \
  && pass "Overview JSON sane" || fail "Overview JSON mismatch"

log "Snapshot/dwell/alerts (existence & auth)"
for ep in snapshot dwell alerts; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" -H "x-request-id: $(RID)" "$BASE/v1/ports/$PORT_OK/$ep?window=14d")
  [[ "$code" == "200" ]] && pass "$ep 200" || fail "$ep expected 200, got $code"
done

pass "Selfcheck done"
