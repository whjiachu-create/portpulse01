-- db/sql/003_core.sql
BEGIN;

-- 数据来源（如需）
CREATE TABLE IF NOT EXISTS sources (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  url  TEXT,
  last_updated TIMESTAMPTZ DEFAULT now()
);

-- 港口快照（多条/天，取最新一条）
CREATE TABLE IF NOT EXISTS port_snapshots (
  id BIGSERIAL PRIMARY KEY,
  unlocode TEXT NOT NULL,
  snapshot_ts TIMESTAMPTZ NOT NULL,
  vessels INT,
  avg_wait_hours DOUBLE PRECISION,
  congestion_score DOUBLE PRECISION,
  src TEXT DEFAULT 'prod'
);
-- 去重与加速
CREATE UNIQUE INDEX IF NOT EXISTS ux_snap_unloc_ts ON port_snapshots(unlocode, snapshot_ts);
CREATE INDEX IF NOT EXISTS ix_snap_unloc_ts_desc ON port_snapshots(unlocode, snapshot_ts DESC);
CREATE INDEX IF NOT EXISTS ix_snap_ts_desc ON port_snapshots(snapshot_ts DESC);

-- 停时（日粒度）
CREATE TABLE IF NOT EXISTS port_dwell (
  unlocode TEXT NOT NULL,
  date DATE NOT NULL,
  dwell_hours DOUBLE PRECISION NOT NULL,
  src TEXT DEFAULT 'prod',
  PRIMARY KEY (unlocode, date)
);

-- 每日最新快照（物化视图）
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_latest_snapshots AS
SELECT DISTINCT ON (unlocode, DATE_TRUNC('day', snapshot_ts))
       unlocode,
       (DATE_TRUNC('day', snapshot_ts) AT TIME ZONE 'UTC')::date AS date,
       snapshot_ts,
       vessels,
       avg_wait_hours,
       congestion_score,
       src
FROM port_snapshots
ORDER BY unlocode, DATE_TRUNC('day', snapshot_ts), snapshot_ts DESC;

-- 支持并发刷新要求的唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_latest ON daily_latest_snapshots(unlocode, date);

-- 刷新函数
CREATE OR REPLACE FUNCTION refresh_daily_latest_snapshots()
RETURNS void LANGUAGE SQL AS
$$ REFRESH MATERIALIZED VIEW CONCURRENTLY daily_latest_snapshots; $$;

COMMIT;