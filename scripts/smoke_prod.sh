#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://api.useportpulse.com}"

echo "== health =="
curl -fsSI "$BASE/v1/health" | sed -n '1p'

echo "== overview csv (ETag + 304 命中) =="
CSV="$BASE/v1/ports/USLAX/overview?format=csv"
H1=$(curl -fsS -D - -o /dev/null "$CSV")
ET=$(printf '%s' "$H1" | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r/,"");print $2}')
test -n "$ET" || { echo "Missing ETag"; exit 1; }
curl -fsS -D - -o /dev/null -H "If-None-Match: $ET" "$CSV" | awk 'NR==1{print}'
