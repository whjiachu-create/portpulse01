#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-https://api.useportpulse.com}
KEY=${2:-dev_demo_123}

echo "== health =="; curl -fsS "$BASE/v1/health" | jq -c .

echo "== openapi.json (docs) ==";
curl -fsS https://docs.useportpulse.com/openapi.json \
| jq -c '.info.version,.components.securitySchemes.ApiKeyAuth,.security'

echo "== trend gate (401 then 200) ==";
curl -sSI "$BASE/v1/ports/USLAX/trend?days=7" | sed -n '1p';
curl -fsS -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7" | jq '.points|length'

echo "== CSV ETag + 304 ==";
H=$(curl -fsS -D - -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o /dev/null);
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r|\"/,"");print $2}');
curl -fsSI -H "X-API-Key: $KEY" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" | sed -n '1p;/[Ee][Tt][Aa][Gg]/p'
