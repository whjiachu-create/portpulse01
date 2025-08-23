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
    ResponseTimeHeaderMiddleware,   # 新增
    JsonErrorEnvelopeMiddleware,
    DefaultCacheControlMiddleware,
    AccessLogMiddleware,
    SimpleRateLimitMiddleware,
    CacheHeaderMiddleware,
)
from fastapi import FastAPI
import os

# 显式导入路由模块，供 include_router 使用
from app.routers import meta, ports, hs

# ⚠️ 先创建 app，再注册任何中间件
app = FastAPI(title="PortPulse API", version="0.1.0")

# middlewares（先写请求 ID，再写响应时间，确保最外层设置头部）
app.add_middleware(RequestIdMiddleware)
# 尽早加时长头，确保被后续中间件保留
app.add_middleware(ResponseTimeHeaderMiddleware)
# 下面保持原有顺序（可选：AccessLog 放在此处也可以）
app.add_middleware(AccessLogMiddleware)
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(SimpleRateLimitMiddleware, rpm=int(os.getenv("RATE_LIMIT_RPM", "120")))
app.add_middleware(DefaultCacheControlMiddleware)
app.add_middleware(CacheHeaderMiddleware)

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

# 注册路由（各自模块内已定义 tags，可不重复传）
app.include_router(meta.router,  prefix="/v1")
app.include_router(ports.router, prefix="/v1/ports")
app.include_router(hs.router,    prefix="/v1")

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