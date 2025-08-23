#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://api.useportpulse.com}"
UNLOCODE="${UNLOCODE:-USLAX}"
API_HEADER="${API_HEADER:-X-API-Key: dev_key_123}"

echo "== health =="; curl -sS -D - -o /dev/null "$BASE/v1/health" \
 | awk 'BEGIN{IGNORECASE=1}/^(HTTP|cache-control:)/{gsub(/\r/,"");print}'

echo; echo "== overview csv（强 ETag + 304 + HEAD）=="
CSV="$BASE/v1/ports/$UNLOCODE/overview?format=csv"
H1="$(curl -sSI -H "$API_HEADER" "$CSV")"
echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^(HTTP|etag:|cache-control:|vary:|x-csv-source:)/{gsub(/\r/,"");print}'
ETAG="$(echo "$H1" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r/,"");print $2}')"
[ -n "$ETAG" ] || { echo "Missing ETag"; exit 1; }
case "$ETAG" in W/*) echo "Weak ETag ($ETAG)"; exit 1 ;; esac
curl -sS -D - -o /dev/null -H "$API_HEADER" -H "If-None-Match: $ETAG" "$CSV" | sed -n '1p' | grep -q "304" || exit 1
STRONG="${ETAG#W/}"
curl -sS -D - -o /dev/null -H "$API_HEADER" -H "If-None-Match: W/$STRONG" "$CSV" | sed -n '1p' | grep -q "304" || exit 1
echo; echo "-- HEAD =="; curl -sSI -H "$API_HEADER" "$CSV" | sed -n '1,10p'
echo; echo "Prod smoke passed."
