#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-https://api.useportpulse.com}
KEY=${KEY:-dev_demo_123}

echo "== health =="; curl -fsS "$BASE/v1/health" | jq -c .

echo "== auth gate 401 =="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/ports/USLAX/trend?days=7")
if [ "$code" != "401" ]; then
  echo "[FAIL] expected 401 without API key, got $code"; exit 22
else
  echo "[OK] 401 without key"
fi

echo "== with key =="
curl -fsS -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7" | jq '.points|length' >/dev/null
echo "[OK] GET with key"

echo "== CSV ETag 304 =="
H=$(curl -fsS -D - -H "X-API-Key: $KEY" "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o /dev/null)
ET=$(printf "%s" "$H" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r|\"/,"");print $2}')
curl -fsSI -H "X-API-Key: $KEY" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" | sed -n '1p;/[Ee][Tt][Aa][Gg]/p'
