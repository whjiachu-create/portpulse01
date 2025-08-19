# PortPulse Public Beta — 北极星清单（North Star Checklist）

> **目标**：对外可收费、稳定可演示、开发者 5 分钟跑通、业务可迭代。  
> **范围**：`/v1` 稳定通道 + 数据口径/质量 + 观测/告警 + 安全/法务 + 官网/文档 + 计费/税务。  
> **触发器**：默认以后所有决策以 **Public Beta** 标准验收（不再按 MVP）。

---

## 1) 核心产品 & 数据（Core Product & Data）

**SLO/DoD**
- 覆盖：≥ 50 个港口（优先 US/EU/SEA 枢纽），并规划到 100。
- 新鲜度：ETL 周期 ≤ 2h；失败自动重试与补采；每天末尾补齐。
- 质量：缺失/异常值处理、基线校验、快照去重、字段字典（Data Dictionary）。
- 性能：所有 `/v1/*` p95 < 300ms。
- 复盘：任一港口**可回放近 30 天**完整数据，无“空洞日”。

**API 端点**
- `GET /v1/ports/{unlocode}/snapshot`（单点快照）
- `GET /v1/ports/{unlocode}/dwell`（每日停时）
- `GET /v1/ports/{unlocode}/trend?days=…&fields=…&format=json|csv&tz=…`（多天趋势）
- `GET /v1/ports/{unlocode}/overview?format=json|csv`（概览导出）
- `GET /v1/ports/{unlocode}/alerts?window=…`（分位阈值 + 变点检测，返回原因/严重度）
- `GET /v1/hs/{code}/imports?frm=YYYY-MM-01&to=YYYY-MM-01`
- `GET /v1/meta/sources`

**数据文档交付**
- 数据字典（字段、类型、口径、单位、缺失/异常处理、更新频率、来源）。
- 端点示例与真实响应 1:1；OpenAPI（带 `x-version`）与 Changelog。

---

## 2) 平台稳定性 & 可观测性（Platform & Observability）

**必须具备**
- 结构化日志（JSON），包含 `request_id`、端点、耗时、状态码、调用方 key。
- APM/错误追踪（Sentry/Logfire 二选一），保存 30–90 天。
- 外部探针（UptimeRobot/Better Stack）：/v1/health、/ports/* 样本、/hs/* 样本。
- 指标看板：QPS、p50/p95、错误率、各端点用量、Job 成功率/时延。
- 备份：DB 每日快照（RPO ≤ 24h），恢复演练（RTO ≤ 2h），每月拉通一次。
- 灰度/回滚：Railway `staging` + `prod` 双环境；一键回滚文档化。

**验收**
- 任一告警触发后 10 分钟内可定位（日志 + 指标 + Trace）。
- 月度恢复演练记录一次（截图/记录留档）。

---

## 3) 安全 & 合规（Security & Compliance）

**要求**
- API Key：生命周期管理（创建/禁用/轮换），**可识别前缀**（如 `pp_live_…`）。
- 限速：Cloudflare Rate Limiting + 应用层令牌桶（Key/IP 维度双限速）。
- Secrets：Railway/Cloudflare Secrets，最小权限，禁止硬编码。
- WAF：基础规则打开；可按地区/机器人做策略。
- 隐私/合规：Privacy Policy、DPA（数据处理协议模板）、Cookie/日志保留策略（90/180 天）。
- 审计：管理员操作审计、关键配置变更留痕。

**验收**
- 未授权 401/403，字典攻击被限速；基础渗透自检（ZAP/nikto 级）通过。

---

## 4) 开发者体验 & 文档（DX & Docs）

**Docs 站**
- `docs.useportpulse.com`（Docusaurus/Redoc 任一）：Quickstart（cURL/Python/JS Tabs）、
  错误码表、限速、示例 CSV、OpenAPI 下载按钮、Postman/Insomnia 集合。

**SDK（轻量）**
- `portpulse-py` 与 `@portpulse/js`：签名、重试、指数退避、限速友好报错。

**验收**
- 新开发者 **5 分钟拿到首个成功响应**，**15 分钟导出 CSV**。

---

## 5) 官网 & 市场（Website & Marketing）

**站点**
- `useportpulse.com`（Cloudflare Pages）：Home / Product / Solutions（Shipper/Forwarder/Fund） /
  Pricing / Blog / Contact。
- Demo：嵌入 USLAX 概览与样例图表（匿名缓存数据）。
- SEO/Analytics：站点地图、OG、GA4/Clarity。
- 线索表单：HubSpot/Typeform → 自动回执 + 内部 Slack 通知。
- 品牌物料：Logo、色板、Pitch PDF（1 页）。

**验收**
- 根域与 `www` 统一 301 → 官网；官网→试用/文档链路顺畅。

---

## 6) 计费 & 税务（Billing & Tax）

**计费**
- Stripe + Stripe Tax；计划（Starter/Pro/Enterprise）与试用/优惠码；
- 用量计量（按 Key 的请求数/数据量，先粗粒度），超量限速/按月结。
- 客户门户：发票下载、卡片管理、账单地址/税号采集。

**法务**
- TOS、Privacy、DPA、SLA（响应/恢复承诺）、退款/停服政策。

**验收**
- 自助订阅→开票→邮件送达闭环跑通。

---

## 7) 客户成功 & 支持（CS & Support）

- 渠道：`support@useportpulse.com`、Docs 反馈入口、状态订阅页面。
- Onboarding：拿 Key → 白名单 → 冒烟脚本（`scripts/smoke.sh`）→ 示例 Notebook。
- SLA：工单优先级与响应/解决承诺。
- 成功案例：≥ 2 个试点 Before/After。

**验收**
- 新客户 24h 内可跑通；建立每月 NPS 收集。

---

## 8) 公司与治理（Company & Ops）

- 公司设立触发器：MRR ≥ \$3k 或 客户 ≥ 10 → 新加坡主体（之前已评估）。
- 基础财务：记账、银行账户、收款对账 SOP。
- 商标：**PortPulse**（英）与“港脉”（中）第 9/35/42 类（US+CN 起步）。
- 合同与 IP：贡献者许可、承包/顾问协议、NDA 模板。

---

## 9) 指标 & 发布准备（Metrics & Launch Readiness）

**KPI**
- 可用率 ≥ 99.9%、延迟 p95、错误率、数据新鲜度、覆盖港口数。
- 漏斗：官网 → 试用 → 付费转化；MRR、Churn。

**发布前清单**
- 压测报告（并发 & 峰值）、回滚演练记录、备份验证、演示账号；
- 法务页齐全（TOS/Privacy/DPA/SLA）、Status 公布、联系与发票信息可见。

---

## 周节奏（建议每周五打钩）

- [ ] ETL 成功率 & 新鲜度 SLO（p95）合格  
- [ ] 外部探针全部绿；Sentry 无新增高优错误  
- [ ] 备份成功；本周回滚演练记录（至少月度一次）  
- [ ] API 变化 → Changelog 同步  
- [ ] 官网/Docs 更新（至少一处）  
- [ ] 潜在客户跟进与反馈归档  

---

## 负责人（RACI 简版）

| 领域 | 负责（R） | 协同（A/C） |
| --- | --- | --- |
| 数据/ETL | Engineering | Product |
| API & SDK | Engineering | DX |
| 观测/告警 | Engineering | Ops |
| 安全/合规 | Ops | Legal |
| 文档/官网 | DX/Marketing | Product |
| 计费/税务 | Ops/Finance | Legal |
| CS/Onboarding | Support/CS | Product |

> 文件版本：`PUBLIC_BETA.md`，作为**唯一真相来源**（SSOT）。任何优先级/范围调整请先改此文档并在 PR 中审阅。

---

## 执行纲领（Public Beta 对齐｜API + 轻量洞察 Demo）

**定位**：以 “API + 轻量洞察（Demo）” 为对外收费最小闭环，标准按 **Public Beta** 执行。  
**目标**：访客能在 1 分钟内看到 Demo，3 分钟拿到 Key，15 分钟跑通 API；可以在线付款，系统稳定、可回滚、可观测。

### 一、阶段优先级（不与总蓝图冲突，只是落地顺序收敛）
1. **官网首页 + Demo（高优先）**  
   - 根域（useportpulse.com）直达首页，首屏价值 + 动态 Demo（缓存样例数据）+ 明确 CTA（Get API Key / Try API）。  
   - 保留 `/docs` 文档站（Redoc/Docusaurus），但首页优先级高于文档。
2. **计费闭环（Stripe + Stripe Tax + Webhook）**  
   - 访客可直接支付 → 自动发 API Key（邮件）→ 立即调用。  
   - 记录用量（先粗粒度），发票自动化。
3. **开发者体验（DX）**  
   - Quickstart（cURL/Python/JS Tabs）、Postman 集合、OpenAPI 下载、一键示例 CSV。  
   - 轻量 SDK（py/js）：内置签名、重试、限速退避。
4. **端点与数据**  
   - `/trend` 增强：`fields=`、`tz=`、分页。  
   - `/alerts` 升级：分位阈值 + 变点检测，返回 `why`/`severity`。  
   - 数据新鲜度 SLO（如 p95 < 2h）、异常/缺失处理、去重与口径字典。
5. **稳定性与可观测**  
   - 外部探针（UptimeRobot/Better Stack）、结构化日志（JSON）、Sentry/Logfire、每日备份、灰度回滚。
6. **安全与合规**  
   - API Key 前缀（`pp_test_…` / `pp_live_…`）、最小权限、WAF 基线。  
   - **Stripe Webhook 验证**、密钥轮换 SOP、DPA/隐私策略。
7. **客户成功与支持**  
   - `support@useportpulse.com`、/welcome 引导、15 分钟跑通清单、状态订阅。  
   - 事件埋点：`view_demo` / `copy_snippet` / `checkout_success` / `first_200_ok` / `first_csv_download`。
8. **公司治理与触发器**  
   - 设立新加坡主体的触发器不变：MRR ≥ $3k 或 付费客户 ≥ 10。

### 二、映射关系（对照《上线前还需完善的工作》九大版块）
| 蓝图章节 | 本阶段动作（收敛） | 验收口径（DoD） |
|---|---|---|
| 核心产品 & 数据 | `/trend`（fields/tz/分页）、`/alerts`（分位阈值+变点）、数据新鲜度 SLO | 任一港口 30 天可回放零空洞；`/v1/*` p95 < 300ms |
| 平台 & 可观测 | 外部探针、结构化日志、Sentry/Logfire、备份/回滚 | 告警触发后 10 分钟内可定位问题 |
| 安全 & 合规 | API Key 前缀、WAF、最小权限、Stripe Webhook 验证、密钥轮换 SOP | 未授权 401/403；暴力尝试被限速 |
| 开发者体验 & 文档 | Docs + Postman + Quickstart + 轻量 SDK（py/js） | 新用户 15 分钟内可跑通并导出 CSV |
| 官网 & 市场化 | 首页 = 价值 + Demo + CTA；SEO/Analytics；线索表单 | 根域直达首页；转化链路顺畅 |
| 计费 & 税务 | Stripe + Tax + Webhook（自动发 Key）+ 粗粒度用量 | 自助订阅→开票→邮件送达 |
| 客户成功 & 支持 | 支持邮箱、Onboarding、SLA、2 个试点案例 | 新客 24h 内跑通；有 NPS 收集 |
| 公司与治理 | 触发器：MRR≥$3k 或 客户≥10 → 新加坡主体 | 模板齐备（合规/合同/财税） |
| 指标 & 发布就绪 | 可用率/延迟/错误率/新鲜度/转化；回滚演练 | 压测/备份验证/法务页齐全 |

### 三、对齐声明
- 本节为**落地顺序与优先级收敛**，**不替代也不冲突**原蓝图；原九大版块仍是全量边界。  
- 当月执行以本节为准；月度复盘时更新本节并在 Changelog 记录变更。

### 四、上线“硬门槛”清单（Public Beta）
- 官网首页 + Demo 可用；  
- Stripe 收款 + 自动发 Key 可用；  
- `/v1/ports/{code}/overview?format=csv` 可下载；  
- 外部探针全部绿；  
- 回滚演练与备份验证完成；  
- 文档 Quickstart 与 Postman 集合可 15 分钟跑通。

## 执行纲领（Public Beta 对齐｜API + 轻量洞察 Demo）

**定位**：以 “API + 轻量洞察（Demo）” 为对外收费最小闭环，标准按 **Public Beta** 执行。  
**目标**：访客能在 1 分钟内看到 Demo，3 分钟拿到 Key，15 分钟跑通 API；可以在线付款，系统稳定、可回滚、可观测。

### 一、阶段优先级（不与总蓝图冲突，只是落地顺序收敛）
1. **官网首页 + Demo（高优先）**  
   - 根域（useportpulse.com）直达首页，首屏价值 + 动态 Demo（缓存样例数据）+ 明确 CTA（Get API Key / Try API）。  
   - 保留 `/docs` 文档站（Redoc/Docusaurus），但首页优先级高于文档。
2. **计费闭环（Stripe + Stripe Tax + Webhook）**  
   - 访客可直接支付 → 自动发 API Key（邮件）→ 立即调用。  
   - 记录用量（先粗粒度），发票自动化。
3. **开发者体验（DX）**  
   - Quickstart（cURL/Python/JS Tabs）、Postman 集合、OpenAPI 下载、一键示例 CSV。  
   - 轻量 SDK（py/js）：内置签名、重试、限速退避。
4. **端点与数据**  
   - `/trend` 增强：`fields=`、`tz=`、分页。  
   - `/alerts` 升级：分位阈值 + 变点检测，返回 `why`/`severity`。  
   - 数据新鲜度 SLO（如 p95 < 2h）、异常/缺失处理、去重与口径字典。
5. **稳定性与可观测**  
   - 外部探针（UptimeRobot/Better Stack）、结构化日志（JSON）、Sentry/Logfire、每日备份、灰度回滚。
6. **安全与合规**  
   - API Key 前缀（`pp_test_…` / `pp_live_…`）、最小权限、WAF 基线。  
   - **Stripe Webhook 验证**、密钥轮换 SOP、DPA/隐私策略。
7. **客户成功与支持**  
   - `support@useportpulse.com`、/welcome 引导、15 分钟跑通清单、状态订阅。  
   - 事件埋点：`view_demo` / `copy_snippet` / `checkout_success` / `first_200_ok` / `first_csv_download`。
8. **公司治理与触发器**  
   - 设立新加坡主体的触发器不变：MRR ≥ $3k 或 付费客户 ≥ 10。

### 二、映射关系（对照《上线前还需完善的工作》九大版块）
| 蓝图章节 | 本阶段动作（收敛） | 验收口径（DoD） |
|---|---|---|
| 核心产品 & 数据 | `/trend`（fields/tz/分页）、`/alerts`（分位阈值+变点）、数据新鲜度 SLO | 任一港口 30 天可回放零空洞；`/v1/*` p95 < 300ms |
| 平台 & 可观测 | 外部探针、结构化日志、Sentry/Logfire、备份/回滚 | 告警触发后 10 分钟内可定位问题 |
| 安全 & 合规 | API Key 前缀、WAF、最小权限、Stripe Webhook 验证、密钥轮换 SOP | 未授权 401/403；暴力尝试被限速 |
| 开发者体验 & 文档 | Docs + Postman + Quickstart + 轻量 SDK（py/js） | 新用户 15 分钟内可跑通并导出 CSV |
| 官网 & 市场化 | 首页 = 价值 + Demo + CTA；SEO/Analytics；线索表单 | 根域直达首页；转化链路顺畅 |
| 计费 & 税务 | Stripe + Tax + Webhook（自动发 Key）+ 粗粒度用量 | 自助订阅→开票→邮件送达 |
| 客户成功 & 支持 | 支持邮箱、Onboarding、SLA、2 个试点案例 | 新客 24h 内跑通；有 NPS 收集 |
| 公司与治理 | 触发器：MRR≥$3k 或 客户≥10 → 新加坡主体 | 模板齐备（合规/合同/财税） |
| 指标 & 发布就绪 | 可用率/延迟/错误率/新鲜度/转化；回滚演练 | 压测/备份验证/法务页齐全 |

### 三、对齐声明
- 本节为**落地顺序与优先级收敛**，**不替代也不冲突**原蓝图；原九大版块仍是全量边界。  
- 当月执行以本节为准；月度复盘时更新本节并在 Changelog 记录变更。

### 四、上线“硬门槛”清单（Public Beta）
- 官网首页 + Demo 可用；  
- Stripe 收款 + 自动发 Key 可用；  
- `/v1/ports/{code}/overview?format=csv` 可下载；  
- 外部探针全部绿；  
- 回滚演练与备份验证完成；  
- 文档 Quickstart 与 Postman 集合可 15 分钟跑通。

