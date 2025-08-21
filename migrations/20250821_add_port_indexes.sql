-- 索引：快照按时间倒序查最新一条
CREATE INDEX IF NOT EXISTS idx_port_snapshots_unlocode_ts
  ON port_snapshots (unlocode, snapshot_ts DESC);

-- 索引：dwell 按日期范围扫描
CREATE INDEX IF NOT EXISTS idx_port_dwell_unlocode_date
  ON port_dwell (unlocode, date);
