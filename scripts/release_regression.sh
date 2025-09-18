#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://api.useportpulse.com}"
PORT="${PORT:-USLAX}"
API_KEY="pp_live_ee62782b3e1fe11cb77907cab5155a1d"
REPO="${REPO:-whjiachu-create/portpulse01}"
BRANCH="${BRANCH:-main}"

need() { command -v "$1" >/dev/null 2>&1 || return 1; }

echo "=== PortPulse Release Regression ==="
echo "BASE=$BASE PORT=$PORT REPO=$REPO BRANCH=$BRANCH"

command -v jq >/dev/null 2>&1 || { echo "❌ need jq"; exit 1; }

curl -fsS "$BASE/v1/health" >/dev/null && echo "✅ health OK" || { echo "❌ health failed"; exit 1; }
curl -fsS "$BASE/openapi.json" | jq -r '.info.title, .info.version, (.paths|length)'

if [[ -n "$API_KEY" ]]; then
  curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=json" >/dev/null && echo "✅ overview JSON"
  LEN=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/trend?limit=5&format=json" | jq '.points|length')
  echo "trend points len=$LEN"
fi

if need gh; then
  echo "— GitHub status —"
  gh repo set-default "$REPO" >/dev/null 2>&1 || true
  gh api repos/$REPO/commits/$BRANCH | jq -r '.sha, .commit.message' | sed -n '1,2p'
else
  echo "⚠️  gh not installed, skip GitHub checks"
fi

if need railway; then
  echo "— Railway status —"
  railway status || true
  echo "— Railway recent error logs —"
  railway logs --lines=200 | (grep -E "ERROR|Exception|Traceback" || true)
else
  echo "⚠️  railway not installed, skip deploy checks"
fi

echo "✅ Regression done."
