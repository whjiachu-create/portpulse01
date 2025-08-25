# PortPulse 路由与契约硬约束（Invariants）

1. 路由前缀约定
   - router 内**一律写相对路径**（如 `/meta/sources`、`/overview`）。
   - 工厂 `create_app()` 里统一挂前缀：`prefix="/v1"`、`prefix="/v1/ports"`。
   - 禁止在 router 中出现 `/v1/*` 绝对前缀。

2. OpenAPI 契约
   - 关键路径必须存在：`/v1/health`、`/v1/meta/sources`、
     `/v1/ports/{unlocode}/overview`、`/v1/ports/{unlocode}/trend`。
   - 删除或改名任何关键路径必须走 `v1beta` 并更新迁移说明。

3. Pydantic v2 规范
   - 仅使用 `model_config = {"json_schema_extra": ...}`；禁止 `class Config: schema_extra`。
   - 时间字段一律 **UTC** 且 **timezone-aware**（`datetime.now(timezone.utc)`）。

4. HTTP 语义
   - CSV: `text/csv; charset=utf-8`；`Cache-Control: public, max-age=300, no-transform`。
   - `/overview?format=csv` 必须返回**强 ETag**，`HEAD`=200，`If-None-Match` 命中 304。

5. 错误体
   - 统一包裹：`{code, message, request_id}`。