#!/usr/bin/env bash
set -euo pipefail
export BASE=${1:-https://api.useportpulse.com}
export DAYS=${DAYS:-30}
export KEY=${KEY:-dev_demo_123}

echo "== coverage =="
KEY="$KEY" DAYS="$DAYS" bash scripts/check_coverage.sh ports_p1.yaml

echo "== freshness p95 =="
./scripts/freshness_p95.py "$BASE"
