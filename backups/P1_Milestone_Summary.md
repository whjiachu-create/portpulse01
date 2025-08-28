# PortPulse — Public Beta **P1** Milestone (UTC: {{填当前UTC时间}})
Commit: {{填 GIT_COMMIT.txt 里的哈希}}  ·  API: https://api.useportpulse.com  ·  Docs: https://docs.useportpulse.com

## 1) Contract (OpenAPI & Endpoints)
- /v1/health: ✅
- /v1/ports/{unlocode}/trend: ✅
- /v1/ports/{unlocode}/dwell: ✅
- /v1/ports/{unlocode}/snapshot: ✅
（以 `openapi_paths_*.json` 为准）

## 2) HTTP Behavior
- Trend CSV ETag 命中：首抓 200，二抓 **304**（`etag_304_*.txt` 证据）✅
- Cache-Control: `public, max-age=300, no-transform` ✅
- 统一错误体 & x-request-id：✅

## 3) Coverage & Freshness (SLO)
- 覆盖：**67 / 67** 港口，30 天连续（`coverage_*.txt`）✅
- 新鲜度：**p95 ≤ 2h**；本次实测：**p95_h = {{粘 freshness_*.txt 的数值}}** ✅

## 4) Docs & DevEx
- Docs: **200 OK**（`/openapi.json` 可下载）✅
- Quickstart/示例：已具备（后续增强）🟡

## 5) Ops
- Cloudflare 规则：CSV 缓存 & Health Bypass 配置完成 ✅
- 外部探活：待接入 Better Stack / UptimeRobot 🟡
- Sentry：等待可访问时补 DSN 🟡

## 6) Data Dump（留痕）
- 目录：`backups/{{TS}}/data/`（包含 JSON/CSV + snapshot）

> 结论：**P1 准入线达标**（可对外公测）。后续进入 P1+（探活、Sentry、Docs Quickstart、定期 ETL 强化）。