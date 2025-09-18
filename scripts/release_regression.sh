#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://api.useportpulse.com}"
PORT="${PORT:-USLAX}"
API_KEY="${API_KEY:-}"
REPO="${REPO:-whjiachu-create/portpulse01}"
BRANCH="${BRANCH:-main}"

need() { command -v "$1" >/dev/null 2>&1 || return 1; }

echo "=== PortPulse Release Regression ==="
echo "BASE=$BASE PORT=$PORT REPO=$REPO BRANCH=$BRANCH"

command -v jq >/dev/null 2>&1 || { echo "❌ need jq"; exit 1; }

curl -fsS "$BASE/v1/health" >/dev/null && echo "✅ health OK" || { echo "❌ health failed"; exit 1; }
curl -fsS "$BASE/openapi.json" | jq -r '.info.title, .info.version, (.paths|length)'

if [[ -n "$API_KEY" ]]; then
  over() { n=0; until curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/overview?format=json" >/dev/null; do n=$((n+1)); [[ $n -ge 3 ]] && { echo "❌ overview JSON failed after retries"; exit 1; }; echo "↻ retry overview ($n)"; sleep 2; done; echo "✅ overview JSON"; }
  over
  LEN=""
  for i in 1 2 3; do
    LEN=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE/v1/ports/$PORT/trend?limit=5&format=json" | jq '.points|length') && break
    echo "↻ retry trend ($i)"; sleep 2
  done
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
  if railway logs --help 2>&1 | grep -q -- '--lines'; then
    OUT="$(railway logs -- --lines=200)"
  else
    OUT="$(railway logs | tail -n 200)"
  fi
  ERR="$(printf "%s" "$OUT" | grep -E 'ERROR|Exception|Traceback' || true)"
  if [ -n "$ERR" ]; then
    printf "%s\n" "$ERR"
  else
    echo "(no recent errors)"
  fi
else
  echo "⚠️  railway not installed, skip deploy checks"
fi

echo "✅ Regression done."
