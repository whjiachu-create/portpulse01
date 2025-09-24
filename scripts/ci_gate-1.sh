#!/usr/bin/env bash
set -euo pipefail

: "${BASE:=https://api.useportpulse.com}"
: "${API_KEY:?FATAL: API_KEY not set}"

mkdir -p logs
ts=$(date -u +%Y%m%d_%H%M)
{
  echo "=== PortPulse CI Gate @ $ts ==="
  ./scripts/selfcheck.sh
  ./scripts/release_regression.sh
  echo "=== ALL CHECKS PASSED ==="
} 2>&1 | tee "logs/ci_gate_${ts}.log"