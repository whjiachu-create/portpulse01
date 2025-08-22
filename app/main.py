# app/main.py
from __future__ import annotations
import os, time
import asyncpg
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# 添加GZip中间件导入
from fastapi.middleware.gzip import GZipMiddleware

from app.middlewares import (
    RequestIdMiddleware,
    ResponseTimeHeaderMiddleware,  # NEW
    JsonErrorEnvelopeMiddleware,
    DefaultCacheControlMiddleware,
    AccessLogMiddleware,
    SimpleRateLimitMiddleware,
    CacheHeaderMiddleware,
)


# 中间件顺序：先注入 request-id，再统一错误，再打日志
# middlewares（先写请求 ID，再写响应时间，确保最外层设置头部）
app.add_middleware(RequestIdMiddleware)
app.add_middleware(ResponseTimeHeaderMiddleware)
app.add_middleware(SimpleRateLimitMiddleware, rpm=int(os.getenv("RATE_LIMIT_RPM", "120")))
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(DefaultCacheControlMiddleware)  # /v1/health 仍强制 no-store
app.add_middleware(AccessLogMiddleware)

# 添加兜底缓存控制中间件
from app.middlewares import DefaultCacheControlMiddleware
app.add_middleware(DefaultCacheControlMiddleware, default_policy="public, max-age=300")

DB_DSN = os.getenv("DATABASE_URL", "")

@app.on_event("startup")
async def on_startup():
    app.state.pool = None
    app.state.db_error = None
    if not DB_DSN:
        return
    try:
        # pgbouncer 兼容：statement_cache_size=0
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=10,
            statement_cache_size=0,
            timeout=30,
            max_inactive_connection_lifetime=300,
        )
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def on_shutdown():
    pool = getattr(app.state, "pool", None)
    if pool:
        await pool.close()

# 根路径跳转
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs", status_code=307)

# 业务路由
# 说明：meta.router 不带前缀，这里挂 /v1；ports/hs 分别挂 /v1/ports 与 /v1/hs
# 修改: 确保 meta.router 使用 /v1 前缀
app.include_router(meta.router,  prefix="/v1",      tags=["meta"])
app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])
app.include_router(hs.router,    prefix="/v1/hs",    tags=["trade"])

# 调试路由：列出路由（不进 OpenAPI）
@app.get("/__routes", include_in_schema=False)
def list_routes():
    items = []
    for r in app.router.routes:
        path = getattr(r, "path", None)
        methods = list(getattr(r, "methods", []) or [])
        name = getattr(r, "name", None)
        if path:
            items.append({"path": path, "methods": methods, "name": name})
    return items

import hashlib
from fastapi import Response, Request
from fastapi.responses import PlainTextResponse

@app.get("/v1/ports/{unlocode}/overview")
async def get_port_overview(
    unlocode: str,
    request: Request,
    format: str = "json"
):
    port_data = await ports.get_port_overview(unlocode)
    if format == "csv":
        return await ports.get_port_overview_csv(unlocode, request)
    
    return port_data
