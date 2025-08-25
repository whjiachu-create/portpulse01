#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://api.useportpulse.com}"

required_paths=(
  "/v1/health"
  "/v1/sources"
  "/v1/ports/{unlocode}/overview"
  "/v1/ports/{unlocode}/trend"
)

json="$(curl -fsS "$BASE/openapi.json")"
for p in "${required_paths[@]}"; do
  echo "$json" | jq -er --arg p "$p" '.paths[$p]' >/dev/null \
    || { echo "Missing path in OpenAPI: $p"; exit 1; }
done
echo "Contract OK."