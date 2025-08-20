# app/main.py
from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

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
    description="PortPulse & TradeMomentum API",
    version="1.1",
    openapi_url="/openapi.json",
)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# —— OpenAPI：不动路径，只缓存生成结果
def custom_openapi():
    if app.openapi_schema:  # type: ignore[attr-defined]
        return app.openapi_schema  # type: ignore[attr-defined]
    schema = app.openapi()
    app.openapi_schema = schema  # type: ignore[attr-defined]
    return app.openapi_schema  # type: ignore[attr-defined]

app.openapi = custom_openapi  # type: ignore[assignment]


# —— 中间件
app.add_middleware(RequestIdMiddleware)
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(AccessLogMiddleware)


# ========= DB 初始化（非阻塞 + 超时）=========
app.state.pool = None
app.state.db_error = None
DB_DSN = os.getenv("DATABASE_URL")

async def _init_pool_background(dsn: str, timeout: float = 3.0):
    """后台尝试建立连接池；失败仅记录错误，不阻塞启动。"""
    try:
        pool = await asyncio.wait_for(
            asyncpg.create_pool(
                dsn=dsn,
                min_size=1, max_size=10,
                statement_cache_size=0,                 # 兼容 pgbouncer
                max_inactive_connection_lifetime=300,
            ),
            timeout=timeout,
        )
        # 轻探活
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        app.state.pool = pool
        app.state.db_error = None
    except Exception as e:
        app.state.pool = None
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("startup")
async def on_startup():
    # 不阻塞：把 DB 初始化丢到后台
    if DB_DSN:
        asyncio.create_task(_init_pool_background(DB_DSN))

@app.on_event("shutdown")
async def on_shutdown():
    pool = getattr(app.state, "pool", None)
    if pool:
        await pool.close()


# ========= 基础路由 =========
@app.get("/", include_in_schema=False)
async def root():
    # Railway 的健康检查建议直接配 /v1/health，这里保留到 /docs 的 307 便于人类访问
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["meta"])
async def health():
    return {"ok": True, "ts": _now_iso(), "db": getattr(app.state, "db_error", None)}

# 调试：查看已注册路由
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


# ========= 业务路由挂载（统一前缀 /v1）=========
# 约定：
#   meta.router 内部声明 "/sources"    -> 对外 /v1/sources
#   ports.router 内部声明 "/ports"      -> 对外 /v1/ports/...
#   hs.router 内部声明 "/hs"           -> 对外 /v1/hs/...
app.include_router(meta.router,  prefix="/v1")
app.include_router(ports.router, prefix="/v1")
app.include_router(hs.router,    prefix="/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))