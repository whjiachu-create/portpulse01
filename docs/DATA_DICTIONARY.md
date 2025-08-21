# PortPulse 数据字典（v1）
更新时间：见仓库提交历史

## 表：port_snapshots
- unlocode: UN/LOCODE, 例 USLAX
- snapshot_ts: 快照观察时间（UTC）
- vessels: 当时在港或等候的船舶数
- avg_wait_hours: 等泊/靠泊平均等待时长（小时）
- congestion_score: 0-100 拥堵评分（规则详见口径说明）
- src: 数据来源/环境标识（prod/dev…）

唯一键：(unlocode, snapshot_ts)

## 表：port_dwell
- date: 自然日（UTC）
- dwell_hours: 当日停时（小时）
- src: 同上

主键：(unlocode, date)

## 视图：daily_latest_snapshots
- date：该日（UTC）
- 其他字段同 port_snapshots，皆为当日**最新**一条