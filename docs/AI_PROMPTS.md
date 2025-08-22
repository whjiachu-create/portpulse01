# PortPulse AI Prompt Kit (Lingma-first)
版本：v1 · 负责人：@owner · 原则：**一切改动以 Lingma 为准，最小可行变更 + 可复制验证命令 + 规范化提交信息**

> 用法：在 VS Code 的「通义灵码（Lingma）」面板，复制本页相应模板，替换尖括号占位符后直接发送。

---

## A. 开场上下文（首次对话先发一次）
你是 PortPulse 项目的结对工程师。约束：最小改动、保留既有行为、给出可复制命令与 Git 提交信息。仓库是 FastAPI + Railway 部署，已有脚本：
	•	scripts/selfcheck.sh（双阈值：SLOW_SERVER_MS=300，SLOW_E2E_MS=2500）
	•	scripts/health_gate.sh（Post-deploy 连续通过）
	•	.github/workflows/smoke.yml（CI 烟囱）

任何修改，都要：1) 只改必要文件；2) 标注变更点；3) 附本地验证命令；4) 给出 Conventional Commits 的 commit message。
---

## B. 常用任务模板

### B1. 单文件小修（最常用）
目标：在 <文件路径> 做以下小修：
	•	问题：<一句话问题>
	•	期望：<一句话期望>
约束：最小 diff；非相关代码不动；保持接口行为与返回结构不变。
输出：

	1.	补丁（直接给最终代码块, 标注文件路径）
	2.	本地验证命令（含 curl / pytest / bash）
	3.	commit message（feat/fix/docs/ops 等）
### B2. 多文件补丁（跨模块）
任务：实现 <功能/修复>，涉及：
	•	<a.py>：<改动点>
	•	<b.py>：<改动点>
要求：分文件给完整最终版本，并解释“为什么要改”。
并提供：
	•	回滚计划（git 按文件回退命令）
	•	本地验证命令
	•	commit message（含 scope）
### B3. OpenAPI 示例 & 数据字典锚点对齐
目标：对齐 FastAPI 路由的 OpenAPI 示例 & docs/DATA_DICTIONARY.md 锚点：
	•	路由：<GET /v1/ports/{unlocode}/snapshot>
	•	约束：顶层永不返回 null；示例与线上一致（/openapi.json）
输出：

	1.	需要修改的 @router.get 装饰器与 docstring 示例
	2.	如需 schema 调整，给最终代码
	3.	更新 DATA_DICTIONARY.md 的锚点片段
	4.	验证命令（curl + jq/python）
	5.	commit message
### B4. 自检/健康门禁脚本（selfcheck / health_gate）
目标：修改 <scripts/selfcheck.sh 或 scripts/health_gate.sh>：
	•	变更：<描述>
	•	阈值：SLOW_SERVER_MS=<值>，SLOW_E2E_MS=<值>
要求：兼容无 jq 环境；错误码语义清晰；输出彩色标记。
输出：完整脚本、新旧差异点、示例运行输出、commit message
### B5. CI 失败修复（Secrets/环境）
现象：GitHub Actions job <名称> 报错 <粘贴核心日志行>。
请：
	•	列出需要的 Secrets（键名）
	•	给 smoke.yml/selfcheck 最小修改片段
	•	给添加 Secrets 的清单（键名+示例值，占位）
	•	本地复现命令（gh workflow run …）
	•	commit message
### B6. Railway 部署前/后置钩子
目标：让 Railway Pre-deploy/Post-deploy 正确执行脚本：
	•	当前设置：<粘贴截图要点或文本>
	•	期望：Pre-deploy 仅健康门禁，StartCommand 保持 uvicorn；传入 BASE_URL 等。
输出：

	1.	health_gate.sh 需要的 env 清单
	2.	控制台“Pre-deploy Command”建议文本（可直接粘贴）
	3.	失败排查清单（≤10 条）
	4.	如脚本需改，给补丁与 commit message
### B7. 数据库索引/迁移（保障 p95 < 300ms）
目标：为 <表名> 的 <查询模式描述> 加索引，生成迁移 SQL。
约束：只加必要索引；给回滚 SQL；解释为何能命中查询。
输出：
	1.	migrations/add.sql（完整 SQL）
	2.	验证：EXPLAIN 预期/示例
	3.	commit message（db）
### B8. 测试（pytest）
为 <模块/路由> 增加 pytest：
	•	覆盖点：成功/空数据/参数校验
	•	如需 mock，请说明方法
输出：

	1.	tests/<test_xxx.py> 完整文件
	2.	运行命令：pytest -q tests/test_xxx.py
	3.	commit message（test）
### B9. 运维告警（Slack 或无 jq 兼容）
目标：用 scripts/notify_ops.sh 推送自检结果到 Slack（或兼容无 jq 环境）。
输入：selfcheck.out
输出：
	1.	notify_ops.sh 最小修改版（保留无 jq 分支）
	2.	测试命令 & 样例 payload
	3.	commit message（ops）
### B10. 变更日志 / 发行说明
根据以下提交摘要生成 CHANGELOG.md 段落（中文，包含“为什么”“如何验证”）：
	•	<粘贴 git log –oneline 范围>
风格：Keep a Changelog + Conventional Commits 小节。
### B11. 回滚/热修应急
假设最新变更引发 5xx，需要 5 分钟内回滚：
输出：
	1.	快速回滚命令（git revert/checkout）
	2.	验证命令（selfcheck / health_gate）
	3.	事后补救（测试、索引、文档）
### B12. **只看差异，不要重写整文件**（强约束）
请在不重写整文件的前提下，给出“最小可行 diff”。若必须重写，请逐段说明原因，并保持原有 API 行为、数据结构、日志语义；所有无关行禁止改动（包括空格与排序）。
输出：先“修改点清单”，再“最终代码”。
---

## C. 常用验证命令（复制即用）

- 自检（本地）  
  `BASE_URL="https://api.useportpulse.com" API_KEY="dev_key_123" bash scripts/selfcheck.sh`

- Post-deploy 本地模拟  
  `BASE_URL="https://api.useportpulse.com" bash scripts/health_gate.sh`

- OpenAPI 校验  
  `curl -sS -H 'Cache-Control: no-cache' "$BASE_URL/openapi.json" | python3 -m json.tool | head`

- CSV 表头  
  `curl -sS -H "X-API-Key: $API_KEY" "$BASE_URL/v1/ports/USLAX/overview?format=csv" | head -n1`

---

## D. 提交规范（Conventional Commits）
- `feat(ports): ...` 新功能  
- `fix(ports): ...` 修 Bug  
- `docs: ...` 文档/字典/README  
- `ops: ...` 运维脚本/CI/部署  
- `db: ...` 迁移与索引  
- `test: ...` 测试

> 每次提交尽量 “小步快跑、可回滚、可验证”。

---

## E. 协作约定
- **Lingma-first**：所有代码改动先走 Lingma 模板；我方只做粘贴与验证。  
- **最小变更**：尽量只改相关行；不动风格与无关空白。  
- **带验证**：每个改动都必须附带可复制命令。  
- **留痕迹**：提交信息清晰，便于回滚与审计。
