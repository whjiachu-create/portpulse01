#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://api.useportpulse.com}"
CONF="${1:-ports_p1.yaml}"
DAYS="${DAYS:-30}"
jq --version >/dev/null 2>&1 || { echo "jq missing"; exit 127; }

ok=0; miss=0
mapfile -t PORTS < <(yq '.ports[].unlocode' "$CONF")
printf "%-8s  %s\n" "PORT" "points(>=25)"
for p in "${PORTS[@]}"; do
  n=$(curl -sS "$BASE/v1/ports/$p/trend?days=$DAYS" | jq '.points|length' 2>/dev/null || echo 0)
  if [ "${n:-0}" -ge 25 ]; then
    printf "%-8s  OK(%s)\n" "$p" "$n"; ok=$((ok+1))
  else
    printf "%-8s  MISS(%s)\n" "$p" "$n"; miss=$((miss+1))
  fi
done
echo "---"
echo "OK=$ok  MISS=$miss  TOTAL=${#PORTS[@]}"
[ "$miss" -eq 0 ] || exit 1
