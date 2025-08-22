#!/usr/bin/env bash
# scripts/db_verify.sh  (v2)
# 验证关键查询是否命中预期索引，并给出 EXPLAIN(ANALYZE, BUFFERS)。
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL not set}"
UNLOCODE="${UNLOCODE:-USLAX}"

psql_run() {
  # 统一的 psql 调用参数：禁止 pager、出错即停
  psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -P pager=off "$@"
}

echo "=== PortPulse Database Index Verification ==="
echo "DATABASE_URL: ${DATABASE_URL}"
echo "UNLOCODE    : ${UNLOCODE}"

# 1) 最新 snapshot（应命中覆盖索引：idx_snapshots_unloc_ts_cover；目标是 Index Only Scan）
echo
echo "Checking: Latest port snapshot"
echo "Expected index: idx_snapshots_unloc_ts_cover (Index Only Scan ideal)"
SNAP_SQL="
SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score
FROM port_snapshots
WHERE unlocode = '${UNLOCODE}'
ORDER BY snapshot_ts DESC
LIMIT 1;
"
echo "SQL:"
echo "$SNAP_SQL"
echo "--- EXPLAIN ANALYZE ---"
psql_run -c "EXPLAIN (ANALYZE, BUFFERS) $SNAP_SQL"

# 2) 最近 14 天 dwell（应命中：idx_dwell_unloc_date_cover；目标是 Index Only Scan）
echo
echo "Checking: Dwell recent 14d"
echo "Expected index: idx_dwell_unloc_date_cover (Index Only Scan ideal)"
DWELL_SQL="
SELECT date, dwell_hours
FROM port_dwell
WHERE unlocode = '${UNLOCODE}'
ORDER BY date DESC
LIMIT 14;
"
echo "SQL:"
echo "$DWELL_SQL"
echo "--- EXPLAIN ANALYZE ---"
psql_run -c "EXPLAIN (ANALYZE, BUFFERS) $DWELL_SQL"

echo
echo "✅ Done. 观察上面的 'Index Only Scan using ...' 或 'Index Scan using ...' 行与执行时间。"