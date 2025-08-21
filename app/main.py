# app/main.py
from __future__ import annotations
import os, time
import asyncpg
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.middlewares import (
    RequestIdMiddleware,
    JsonErrorEnvelopeMiddleware,
    AccessLogMiddleware,
)
from app.routers import meta, ports, hs

app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    description="PortPulse & TradeMomentum API",
    openapi_url="/openapi.json",
)

# 中间件顺序：先注入 request-id，再统一错误，再打日志
app.add_middleware(RequestIdMiddleware)
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(AccessLogMiddleware)
from app.middlewares import CacheControlMiddleware
app.add_middleware(CacheControlMiddleware)
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

# 健康检查（DB 可选）
@app.get("/v1/health", tags=["meta"])
async def health():
    # 统一返回：ok/ts/db（db 异常时返回错误摘要字符串）
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    pool = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": True, "ts": now_iso, "db": None}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": now_iso, "db": None}
    except Exception as e:
        return {"ok": False, "ts": now_iso, "db": f"{type(e).__name__}: {e}"}

# 业务路由
# 说明：meta.router 不带前缀，这里挂 /v1；ports/hs 分别挂 /v1/ports 与 /v1/hs
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