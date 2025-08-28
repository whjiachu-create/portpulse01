#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-https://api.useportpulse.com}
TS=$(date -u +%Y%m%dT%H%M%SZ)
DIR="backups/p1_$TS"; mkdir -p "$DIR"
echo "[*] saving to $DIR"
curl -fsS "$BASE/openapi.json" -o "$DIR/openapi.json"
curl -fsS "$BASE/v1/health" | jq . > "$DIR/health.json"
curl -fsS -H "X-API-Key: ${2:-dev_demo_123}" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o "$DIR/USLAX_7d.csv"
DAYS=30 bash scripts/check_coverage.sh ports_p1.yaml > "$DIR/coverage.txt"
./scripts/freshness_p95.py "$BASE"              > "$DIR/freshness.txt" || true
echo "[ok] backup done → $DIR"
