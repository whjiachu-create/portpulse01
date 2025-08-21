-- 幂等写入示例（存在则忽略）
-- 快照
INSERT INTO port_snapshots (unlocode, snapshot_ts, vessels, avg_wait_hours, congestion_score, src)
VALUES ('USLAX', '2025-08-14T13:20:02+00', 160, 3.92, 60.0, 'prod')
ON CONFLICT (unlocode, snapshot_ts) DO NOTHING;

-- 日停时
INSERT INTO port_dwell (unlocode, date, dwell_hours, src)
VALUES ('USNYC', '2025-08-14', 2.66, 'prod')
ON CONFLICT (unlocode, date) DO UPDATE SET
  dwell_hours = EXCLUDED.dwell_hours,
  src         = EXCLUDED.src;