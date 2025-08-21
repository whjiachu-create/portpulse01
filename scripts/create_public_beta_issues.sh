#!/usr/bin/env bash
set -euo pipefail

#----------------------------------------
# Auto-issue bootstrap for Public Beta
#----------------------------------------

# 解析当前仓库 owner/repo（基于 origin）
REPO="$(git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)([^/]+/[^.]+)(\.git)?#\2#')"
if [[ -z "${REPO}" ]]; then
  echo "❌ 无法识别 GitHub 仓库（请确保已设置 origin 远端）。"
  exit 1
fi
echo "📦 Target repo: ${REPO}"

# 里程碑名称（可改）
MILESTONE="Public Beta"
MILESTONE_DESC="对外可收费、稳定可演示的发布标准（详见 PUBLIC_BETA.md）"
# 如需设置截止日期，取消下一行注释并设成 YYYY-MM-DD
# DUE_ON="2025-10-15"

# 统一创建/更新标签
echo "🏷️  创建/更新标签..."
gh label create "stage:public-beta" --color BFDADC --description "Public Beta 范畴" -R "$REPO" 2>/dev/null || true
gh label create "priority:high"     --color D93F0B --description "高优先级"      -R "$REPO" 2>/dev/null || true
gh label create "area:data"         --color 1D76DB --description "数据/ETL"      -R "$REPO" 2>/dev/null || true
gh label create "area:api"          --color 0E8A16 --description "API/后端"      -R "$REPO" 2>/dev/null || true
gh label create "area:observability"--color FBCA04 --description "日志/监控/告警" -R "$REPO" 2>/dev/null || true
gh label create "area:security"     --color 5319E7 --description "安全/合规"      -R "$REPO" 2>/dev/null || true
gh label create "area:docs"         --color C2E0C6 --description "文档/DX/SDK"    -R "$REPO" 2>/dev/null || true
gh label create "area:website"      --color FEF2C0 --description "官网/市场"      -R "$REPO" 2>/dev/null || true
gh label create "area:billing"      --color E99695 --description "计费/税务"      -R "$REPO" 2>/dev/null || true
gh label create "area:cs"           --color 5319E7 --description "客户成功/支持"  -R "$REPO" 2>/dev/null || true
gh label create "area:ops"          --color 0052CC --description "运维/公司治理"  -R "$REPO" 2>/dev/null || true
gh label create "type:task"         --color 000000 --description "任务"          -R "$REPO" 2>/dev/null || true

# 创建里程碑（若已存在则跳过）
echo "🏁 创建/查找 Milestone..."
if gh milestone list -R "$REPO" --state open | grep -q "^${MILESTONE}\b"; then
  echo "ℹ️  里程碑已存在：${MILESTONE}"
else
  if [[ -n "${DUE_ON:-}" ]]; then
    gh milestone create "$MILESTONE" -R "$REPO" -d "$MILESTONE_DESC" --due-on "$DUE_ON"
  else
    gh milestone create "$MILESTONE" -R "$REPO" -d "$MILESTONE_DESC"
  fi
fi

MILESTONE_NUMBER="$(gh api -R "$REPO" repos/{owner}/{repo}/milestones -q '.[] | select(.title=="'"$MILESTONE"'") | .number')"
echo "✅ Milestone #$MILESTONE_NUMBER"

# 小工具：创建 Issue（body 从 STDIN）
create_issue () {
  local title="$1"; shift
  local labels="$1"; shift
  local body_file
  body_file="$(mktemp)"
  cat > "$body_file"

  # labels 使用空格分隔
  local label_flags=""
  for l in $labels; do
    label_flags="$label_flags -l $l"
  done

  gh issue create -R "$REPO" \
    -t "$title" \
    -F "$body_file" \
    -m "$MILESTONE_NUMBER" \
    $label_flags \
    >/dev/null

  rm -f "$body_file"
  echo "  • Created: $title"
}

echo "📝 批量创建 Issues..."

# 1. 里程碑总览
create_issue "Public Beta 里程碑总览（燃尽 & 跟踪）" "stage:public-beta type:task" <<'MD'
**目标**：本里程碑所有任务可视化跟踪与每周复盘。  
- [ ] 每周五更新燃尽：完成/剩余任务、风险与决策记录  
- [ ] 每周更新发布说明：本周范围变更、已完结与下周计划  
- [ ] 与 `PUBLIC_BETA.md` 保持同步（任何调整先改文档，再改 Issue）
MD

# 2. 数据覆盖 & 质量
create_issue "数据覆盖：港口 50 → 100（优先 US/EU/SEA）" "area:data stage:public-beta priority:high type:task" <<'MD'
**验收**： ≥50 个港口上线（规划到 100），均满足 30 天可回放、零空洞。  
- [ ] 港口清单与优先级（US/EU/SEA 枢纽）  
- [ ] 每港口数据源与抓取方式确认（频率/窗口/授权）  
- [ ] 回放脚本：抽查 10 个港口近 30 天无“空洞日”  
- [ ] 采集失败自动重试与补采策略
MD

create_issue "ETL 新鲜度 SLO（p95≤2h）与失败自动补采" "area:data stage:public-beta priority:high type:task" <<'MD'
**验收**：任一数据集 p95 延迟≤2h；失败自动补采；每日末尾校准。  
- [ ] 调度：GitHub Actions + 重试策略（指数退避/并发控制）  
- [ ] 失败回补：差异清单 + 对账机制  
- [ ] 新鲜度探针：Dashboard 指标 + 告警（>阈值报警）
MD

create_issue "数据质量：缺失/异常处理、基线校验、快照去重" "area:data stage:public-beta type:task" <<'MD'
**验收**：字段字典齐全；异常值拦截与告警；快照去重稳定。  
- [ ] 字段字典（口径/单位/缺失策略/更新频率）  
- [ ] 异常检测：分位/3σ/阈值混合  
- [ ] 去重逻辑：主键/时间窗/幂等
MD

# 3. API 完善
create_issue "API 拓展：/trend fields/tz/pagination；/overview CSV；错误统一" "area:api stage:public-beta type:task" <<'MD'
**验收**：  
- `GET /v1/ports/{unlocode}/trend?fields=...&tz=...&page=...`  
- `GET /v1/ports/{unlocode}/overview?format=csv` CSV 头部与示例一致  
- 统一错误体：`{code,message,hint,request_id}`  
- [ ] OpenAPI 示例与真实响应一致
MD

create_issue "告警升级：分位阈值 + 变点检测（含原因/严重度）" "area:api stage:public-beta priority:high type:task" <<'MD'
**验收**：/alerts 返回 `type/severity/why`，可配置窗口与灵敏度。  
- [ ] 分位阈值（p90/p95）+ 变点检测（CUSUM/贝叶斯）  
- [ ] 解释字段：基线、变化幅度、近 7/14/30 天对比  
- [ ] 示例与可视化（Docs/Notebook）
MD

create_issue "OpenAPI 版本化与 v1/v1beta 冻结策略" "area:api stage:public-beta type:task" <<'MD'
**验收**：/v1 稳定；新实验进入 /v1beta；OpenAPI 加 `x-version` 与 Changelog。  
- [ ] 版本策略说明  
- [ ] 变更公告模板与 Deprecation 周期（≥90 天）
MD

# 4. 观测与告警
create_issue "统一日志与 APM（Sentry/Logfire），外部探针" "area:observability stage:public-beta priority:high type:task" <<'MD'
**验收**：结构化日志含 request_id；Sentry 捕获错误；外部探针覆盖核心端点。  
- [ ] JSON 日志（端点/延迟/状态码/key）  
- [ ] Sentry/Logfire 接入与告警  
- [ ] UptimeRobot/Better Stack 探针
MD

create_issue "指标看板与备份恢复演练（RPO≤24h，RTO≤2h）" "area:observability stage:public-beta type:task" <<'MD'
**验收**：QPS/延迟/错误率/用量看板；每月 DR 演练记录一次。  
- [ ] 仪表盘链接与阈值告警  
- [ ] 备份快照与恢复演练
MD

# 5. 安全/合规
create_issue "速率限制 + WAF + API Key 生命周期" "area:security stage:public-beta priority:high type:task" <<'MD'
**验收**：未授权 401/403；暴力/爬虫受限；Key 支持创建/禁用/轮换（前缀可识别）。  
- [ ] Cloudflare Rate Limiting（IP/Key）  
- [ ] 应用内令牌桶（突发保护）  
- [ ] WAF 基本规则
MD

create_issue "隐私与合规：Privacy/DPA/日志保留策略" "area:security stage:public-beta type:task" <<'MD'
**验收**：发布 Privacy、DPA 模板；日志/数据留存策略 90/180 天。  
- [ ] 文档上线  
- [ ] 审核与对外可见链接
MD

# 6. 文档 & SDK
create_issue "Docs 站（Docusaurus/Redoc）与示例" "area:docs stage:public-beta priority:high type:task" <<'MD'
**验收**：Quickstart（cURL/Python/JS）、错误码表、限速说明、示例 CSV、OpenAPI 下载。  
- [ ] docs.useportpulse.com 发布  
- [ ] Postman/Insomnia 集合
MD

create_issue "SDK：portpulse-py / @portpulse/js（重试/限速/签名）" "area:docs stage:public-beta type:task" <<'MD'
**验收**：开发者可 15 分钟内用 SDK 导出 CSV。  
- [ ] Python 包（pip）  
- [ ] JS 包（npm）
MD

# 7. 官网/市场
create_issue "官网与 Demo（匿名缓存数据）" "area:website stage:public-beta priority:high type:task" <<'MD'
**验收**：Home/Product/Solutions/Pricing/Contact；USLAX 示例嵌入；GA4/SEO 完成。  
- [ ] Cloudflare Pages 部署  
- [ ] 线索表单（邮件/Slack 通知）
MD

# 8. 计费/税务
create_issue "Stripe + Stripe Tax（计划/发票/超量）" "area:billing stage:public-beta priority:high type:task" <<'MD'
**验收**：自助订阅→开票→邮件送达；超量限速或按月结。  
- [ ] 价格档位与优惠码  
- [ ] 客户门户（发票/卡片/税号）
MD

# 9. 客户成功/支持
create_issue "Onboarding & 支持通道 & 案例" "area:cs stage:public-beta type:task" <<'MD'
**验收**：新客户 24h 内跑通；2 个试点案例上线；SLA 公布。  
- [ ] support@useportpulse.com  
- [ ] 冒烟脚本/Notebook 指南
MD

# 10. 公司/治理
create_issue "公司设立触发器与法务模板（新加坡主体）" "area:ops stage:public-beta type:task" <<'MD'
**验收**：MRR≥$3k 或 客户≥10 → 触发公司设立；合同/NDA/贡献者许可模板就绪。  
- [ ] 商标（PortPulse/港脉）9/35/42 类（US+CN）  
- [ ] 财税 SOP
MD

echo "✅ 全部 Issues 已创建并挂到 Milestone：${MILESTONE}"
