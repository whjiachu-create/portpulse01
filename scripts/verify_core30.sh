#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?Please export BASE, e.g. https://api.useportpulse.com}"
: "${API_KEY:?Please export API_KEY}"

read -r -d '' CORE30 <<'PORTS'
USLAX
USLGB
USNYC
USSAV
USCHS
USORF
USHOU
USSEA
USOAK
USMIA
NLRTM
BEANR
DEHAM
DEBRV
FRLEH
GBFXT
GBLGP
ESVLC
ESALG
GRPIR
CNSHA
CNNGB
CNSZX
CNTAO
KRPUS
SGSIN
MYTPP
THLCH
INNSA
INMUN
PORTS

ok=1
printf "%-6s %s\n" "PORT" "N(days)"
echo "-----------------"

while read -r p; do
  [[ -z "$p" ]] && continue
  url="$BASE/v1/ports/$p/trend?window=30&format=json"
  n=$(curl -fsS -H "X-API-Key: $API_KEY" "$url" | jq -r '.points|length // 0')
  printf "%-6s %2s\n" "$p" "$n"
  [[ "$n" -eq 30 ]] || ok=0
done <<< "$CORE30"

if [[ $ok -eq 0 ]]; then
  echo "❌ Not all ports have 30 points"
  exit 1
else
  echo "✅ Core30 all have 30 points."
fi
