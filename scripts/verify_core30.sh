#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?Please export BASE}"
: "${API_KEY:?Please export API_KEY}"
WIN="${WIN:-30}"

CORE30=(USLAX USLGB USNYC USSAV USCHS USORF USHOU USSEA USOAK USMIA
        NLRTM BEANR DEHAM DEBRV FRLEH GBFXT GBLGP ESVLC ESALG GRPIR
        CNSHA CNNGB CNSZX CNTAO KRPUS SGSIN MYTPP THLCH INNSA INMUN)

fail=0
for p in "${CORE30[@]}"; do
  n=$(curl -fsS -H "X-API-Key: $API_KEY" \
      "$BASE/v1/ports/$p/trend?window=$WIN&format=json" | jq -r '.points|length // 0')
  printf "%-6s %2s\n" "$p" "$n"
  [[ "$n" -eq "$WIN" ]] || fail=$((fail+1))
done
echo "----"
[[ "$fail" -eq 0 ]] && echo "✅ Core30 OK ($WIN/30d all green)" || \
  (echo "❌ $fail port(s) not $WIN days"; exit 1)