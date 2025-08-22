-- 注意：CONCURRENTLY 不能放在事务里，psql 会逐条执行即可
SET lock_timeout = '2s';
SET statement_timeout = '5min';

-- 1) sources：支持 /v1/sources?since_hours=X 按最近更新时间过滤/排序
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sources_last_updated
ON sources (last_updated DESC);

-- 2) port_snapshots：支持 overview/snapshot 最新一条 & trend 按日期范围
-- （最常见的过滤是按 unlocode + 时间，排序取最新）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshots_unloc_ts
ON port_snapshots (unlocode, snapshot_ts DESC);

-- 覆盖索引（包含常取字段，减少回表；老版本 PG 兼容就留着，也可跳过）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_snapshots_unloc_ts_cover
ON port_snapshots (unlocode, snapshot_ts DESC)
INCLUDE (vessels, avg_wait_hours, congestion_score, src, src_loaded_at);

-- 3) port_dwell：支持 dwell/alerts 最近 N 天
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dwell_unloc_date
ON port_dwell (unlocode, date DESC);

-- 覆盖常用字段（alerts 会用 dwell_hours 参与计算）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dwell_unloc_date_cover
ON port_dwell (unlocode, date DESC)
INCLUDE (dwell_hours, src);
