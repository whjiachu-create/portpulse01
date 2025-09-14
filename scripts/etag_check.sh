#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?Please export BASE}"
: "${API_KEY:?Please export API_KEY}"
PORT="${PORT:-USLAX}"
WIN="${WIN:-30}"
KIND="${KIND:-trend}"  # trend 或 overview

if [[ "$KIND" == "trend" ]]; then
  URL="$BASE/v1/ports/$PORT/trend?window=$WIN&format=csv"
else
  URL="$BASE/v1/ports/$PORT/overview?format=csv"
fi

tmpdir=$(mktemp -d)
h1="$tmpdir/h1.txt"; b1="$tmpdir/b1.csv"
h2="$tmpdir/h2.txt"

# 第一次 GET，拿强 ETag
curl -fsS -D "$h1" -o "$b1" -H "X-API-Key: $API_KEY" "$URL" >/dev/null
ETAG=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^ETag:/{gsub("\r","",$2);print $2}' "$h1")
SRC=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^x-csv-source:/{gsub("\r","",$2);print $2}' "$h1")
LEN=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^Content-Length:/{gsub("\r","",$2);print $2}' "$h1")
echo "ETAG=$ETAG SRC=$SRC LEN=$LEN"

# 第二次请求带 If-None-Match，期望 304（或 200 但 ETag 不变）
code=$(curl -fsS -o /dev/null -w '%{http_code}' \
  -H "X-API-Key: $API_KEY" -H "If-None-Match: $ETAG" "$URL")
echo "Revalidate HTTP $code"

if [[ "$code" == "304" ]]; then
  echo "✅ ETag stable (304)"
else
  # 兜底：再取一次头，确认 ETag 未变化
  curl -fsS -I -o "$h2" -H "X-API-Key: $API_KEY" "$URL" >/dev/null
  ETAG2=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^ETag:/{gsub("\r","",$2);print $2}' "$h2")
  if [[ "$ETAG" == "$ETAG2" ]]; then
    echo "✅ ETag stable (200 but same ETag)"
  else
    echo "❌ ETag changed"; exit 1
  fi
fi