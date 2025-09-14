#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?Please export BASE}"
: "${API_KEY:?Please export API_KEY}"

PORT=${1:?Usage: scripts/etag_check.sh USLAX [window=30] [trend|overview]}
WIN=${2:-30}
KIND=${3:-trend}  # trend | overview

if [[ "$KIND" == "trend" ]]; then
  URL="$BASE/v1/ports/$PORT/trend?window=$WIN&format=csv"
else
  URL="$BASE/v1/ports/$PORT/overview?format=csv"
fi

tmpdir=$(mktemp -d)
h1="$tmpdir/h1.txt"
h2="$tmpdir/h2.txt"
body="$tmpdir/body.csv"

echo "Checking $KIND for $PORT (window=$WIN)"
echo "URL: $URL"

# 1) 初次 GET，拿到 ETag
curl -fsS -D "$h1" -o "$body" -H "X-API-Key: $API_KEY" "$URL" >/dev/null
ETAG=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^ETag:/{gsub("\r","",$2);print $2}' "$h1")
CLEN=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^Content-Length:/{gsub("\r","",$2);print $2}' "$h1")
SRC=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^x-csv-source:/{gsub("\r","",$2);print $2}' "$h1")

echo "ETAG=$ETAG"
echo "LEN=$CLEN  SRC=${SRC:-n/a}"

# 2) GET + If-None-Match 复验证
code=$(curl -fsS -o /dev/null -w '%{http_code}' \
  -H "X-API-Key: $API_KEY" -H "If-None-Match: $ETAG" "$URL")
echo "GET revalidate -> HTTP $code  (304 means cache revalidated)"

# 3) HEAD + If-None-Match 再验证，并对比 ETag 是否一致
code_head=$(curl -fsS -I -o "$h2" -w '%{http_code}' \
  -H "X-API-Key: $API_KEY" -H "If-None-Match: $ETAG" "$URL")
ETAG2=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^ETag:/{gsub("\r","",$2);print $2}' "$h2")
echo "HEAD revalidate -> HTTP $code_head ; ETag(head)=$ETAG2"

if [[ "$ETAG" == "$ETAG2" ]]; then
  echo "ETag stable ✅"
else
  echo "ETag changed ❌"
  exit 2
fi
