#!/usr/bin/env bash
set -euo pipefail
curl -fsSL https://api.useportpulse.com/openapi.json -o docs/openapi.json
git add docs/openapi.json
git diff --cached --quiet || git commit -m "docs: update openapi.json from prod"
git pull --rebase origin main || true
git push origin main || true
echo "[ok] docs synced (if push succeeded)"
