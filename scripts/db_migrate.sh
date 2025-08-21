#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL required}"

echo ">> applying db/sql/003_core.sql"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/003_core.sql

echo ">> refresh daily_latest_snapshots"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT refresh_daily_latest_snapshots();"
echo "✅ done"