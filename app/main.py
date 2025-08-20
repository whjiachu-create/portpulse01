# app/main.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import asyncpg
from fastapi import FastAPI, RedirectResponse

# 中间件（我们之前已提交）
from app.middlewares import (
    RequestIdMiddleware,
    JsonErrorEnvelopeMiddleware,
    AccessLogMiddleware,
)

# 业务路由
from app.routers import meta, ports, hs


# -------------------------------------------------
# App 基础信息 & OpenAPI
# -------------------------------------------------
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    description="PortPulse & TradeMomentum API",
    version="1.1",
    openapi_url="/openapi.json",
)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# 自定义 OpenAPI（只设元信息，不改路径）
def custom_openapi():
    if app.openapi_schema:  # type: ignore[attr-defined]
        return app.openapi_schema  # type: ignore[attr-defined]
    schema = app.openapi()
    # 可按需附加自定义字段
    app.openapi_schema = schema  # type: ignore[attr-defined]
    return app.openapi_schema  # type: ignore[attr-defined]

app.openapi = custom_openapi  # type: ignore[assignment]


# -------------------------------------------------
# 中间件
# -------------------------------------------------
app.add_middleware(RequestIdMiddleware)         # 在响应头注入 x-request-id
app.add_middleware(JsonErrorEnvelopeMiddleware) # 统一错误响应体结构
app.add_middleware(AccessLogMiddleware)         # 简单访问日志


# -------------------------------------------------
# DB 连接池（可选）
# 说明：
# - 未配置 DATABASE_URL 时，不创建连接池（/v1/health 仍返回 ok）。
# - 为兼容 pgbouncer，禁用 prepared statement 缓存：statement_cache_size=0
# -------------------------------------------------
app.state.pool = None
app.state.db_error = None

DB_DSN = os.getenv("DATABASE_URL")

@app.on_event("startup")
async def on_startup():
    app.state.pool = None
    app.state.db_error = None

    if not DB_DSN:
        return

    try:
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=10,
            statement_cache_size=0,           # 关键：禁用 statement 缓存以适配 pgbouncer
            max_inactive_connection_lifetime=300,
        )
        # 轻量探活，避免阻塞启动
        async with app.state.pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.fetchval("SELECT 1;")
    except Exception as e:  # 不让启动失败，健康检查里报告
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def on_shutdown():
    pool = getattr(app.state, "pool", None)
    if pool:
        await pool.close()


# -------------------------------------------------
# 基础路由
# -------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    # 根路径跳转到 Swagger
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["meta"])
async def health():
    db_status: Any = None
    # 若有连接池，尝试一次极短查询；失败也不抛异常
    try:
        if app.state.pool:
            async with app.state.pool.acquire() as conn:  # type: ignore[union-attr]
                await conn.fetchval("SELECT 1;")
            db_status = None
        else:
            db_status = None
    except Exception as e:
        db_status = f"{type(e).__name__}: {e}"

    return {"ok": True, "ts": _now_iso(), "db": db_status}

# 仅用于排查（不会出现在 OpenAPI 里）
@app.get("/_/routes", include_in_schema=False)
async def list_routes() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for r in app.router.routes:
        path = getattr(r, "path", None)
        name = getattr(r, "name", None)
        methods = sorted(list(getattr(r, "methods", set())))
        if path:
            items.append({"path": path, "name": name, "methods": methods})
    return items


# -------------------------------------------------
# 业务路由挂载（统一挂 /v1 前缀）
# 约定：
#   - meta.router 内部声明 path 如 "/sources"，对外即 "/v1/sources"
#   - ports.router 内部声明前缀 "/ports"，对外即 "/v1/ports/..."
#   - hs.router   内部声明前缀 "/hs"    ，对外即 "/v1/hs/..."
# -------------------------------------------------
app.include_router(meta.router,  prefix="/v1")
app.include_router(ports.router, prefix="/v1")
app.include_router(hs.router,    prefix="/v1")


# 本地调试：python -m app.main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))