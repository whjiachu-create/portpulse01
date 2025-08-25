# 【任务名】—— 背景/目标/验收

## 不可动区（Hard Rules，若不理解请停手）
- router 内**相对路径**，工厂里统一 `prefix="/v1"`。
- 不得改动关键路径名：`/v1/meta/sources`、`/v1/ports/{unlocode}/overview|trend`。
- Pydantic v2：仅用 `model_config`；禁止 `class Config`。
- CSV/ETag/HEAD 语义不能改变。

## 要做什么（What）
- <具体改动>

## 具体 diff（只改这些文件）
<code fences with unified diff>

## 本地自测（必须全部通过）
<shell commands to run curl/pytest>

## 提交信息（Commit message）
<conventional style>