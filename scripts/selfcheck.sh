#!/usr/bin/env bash
# scripts/selfcheck.sh
set -euo pipefail

: "${BASE_URL:?BASE_URL not set}"; : "${API_KEY:?API_KEY not set}"

echo "🔎 Smoke @ ${BASE_URL}"

# 1) health（无需鉴权）
echo -n "1) /v1/health ... "
curl -fsS -H "Accept: application/json" "${BASE_URL}/v1/health" >/dev/null && echo "OK"

# 2) sources（无需鉴权）
echo -n "2) /v1/sources ... "
curl -fsS -H "Accept: application/json" "${BASE_URL}/v1/sources" >/dev/null && echo "OK"

# 3) snapshot（鉴权）
echo -n "3) /v1/ports/USLAX/snapshot ... "
curl -fsS -H "Accept: application/json" -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/v1/ports/USLAX/snapshot" >/dev/null && echo "OK"

# 4) dwell（鉴权）
echo -n "4) /v1/ports/USLAX/dwell?days=14 ... "
curl -fsS -H "Accept: application/json" -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/v1/ports/USLAX/dwell?days=14" >/dev/null && echo "OK"

# 5) overview（csv，鉴权）
echo -n "5) /v1/ports/USLAX/overview?format=csv ... "
curl -fsS -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/v1/ports/USLAX/overview?format=csv" | head -n 1 | grep -q "unlocode,as_of" && echo "OK"

# 6) alerts（鉴权）
echo -n "6) /v1/ports/USNYC/alerts?window=14d ... "
curl -fsS -H "Accept: application/json" -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/v1/ports/USNYC/alerts?window=14d" >/dev/null && echo "OK"

# 7) trend（鉴权）
echo -n "7) /v1/ports/USLAX/trend ... "
curl -fsS -H "Accept: application/json" -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/v1/ports/USLAX/trend?days=30&fields=vessels,avg_wait_hours&limit=30&offset=0" >/dev/null && echo "OK"

echo "✅ All green"