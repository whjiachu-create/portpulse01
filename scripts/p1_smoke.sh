#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-https://api.useportpulse.com}
KEY=${2:-dev_demo_123}

echo "== health =="
code=$(curl -sS -D /tmp/h.txt "$BASE/v1/health" -o /tmp/health.json -w "%{http_code}")
if [ "$code" != "200" ]; then
  echo "--- headers ---"; cat /tmp/h.txt || true
  echo "--- body ---"; cat /tmp/health.json || true
  echo "ERROR: /v1/health not 200, got $code"
  exit 22
fi
jq -c . /tmp/health.json 2>/dev/null || cat /tmp/health.json

echo "== openapi.json (docs) =="
curl -fsS https://docs.useportpulse.com/openapi.json \
| jq -c '.info.version,.components.securitySchemes.ApiKeyAuth,.security'

echo "== trend gate (401 then 200) =="
curl -sSI "$BASE/v1/ports/USLAX/trend?days=7" | sed -n '1p'
curl -fsS -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7" | jq '.points|length'

echo "== CSV ETag + 304 =="
H=$(curl -fsS -D - -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o /dev/null)
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r|\"/,"");print $2}')
curl -fsSI -H "X-API-Key: $KEY" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" | sed -n '1p;/[Ee][Tt][Aa][Gg]/p'
