# app/main.py
from __future__ import annotations

import os, urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional, Dict
import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.openapi.utils import get_openapi

from app.deps import get_conn, require_api_key
from app.middlewares import RequestIdMiddleware, JsonErrorEnvelopeMiddleware, AccessLogMiddleware

# 子路由
from app.routers import meta, ports, hs
from app.routers import ports_extra

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_dsn(raw: str) -> str:
    if "?" in raw:
        base, qs = raw.split("?", 1)
    else:
        base, qs = raw, ""
    params = dict(urllib.parse.parse_qsl(qs, keep_blank_values=True))
    params.setdefault("sslmode", "require")
    params.setdefault("connect_timeout", "10")
    return f"{base}?{urllib.parse.urlencode(params)}"

RAW_DSN = os.getenv("DATABASE_URL", "").strip()
DB_DSN: Optional[str] = _normalize_dsn(RAW_DSN) if RAW_DSN else None

app = FastAPI(title="PortPulse API", version="1.2", openapi_url="/openapi.json")

# OpenAPI：全局 API Key 方案，确保 /docs 右上角有 Authorize
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="PortPulse API",
        version="1.2",
        description="Operational port metrics and trade flows",
        routes=app.routes,
    )
    comps = schema.setdefault("components", {})
    comps.setdefault("securitySchemes", {})["APIKeyHeader"] = {
        "type": "apiKey", "in": "header", "name": "X-API-Key"
    }
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return schema
app.openapi = custom_openapi

# 中间件
app.add_middleware(RequestIdMiddleware)
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_headers=["*"], allow_methods=["*"],
)

# 启动/关闭：连接池
@app.on_event("startup")
async def startup():
    app.state.pool = None
    app.state.db_error = None
    if not DB_DSN:
        app.state.db_error = "DATABASE_URL not set"
        return
    try:
        app.state.pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=5)
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown():
    pool = getattr(app.state, "pool", None)
    if pool: await pool.close()

# 根路径 → /docs
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)

# 健康检查（含 DB）
@app.get("/v1/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    if not getattr(app.state, "pool", None):
        return {"ok": False, "ts": _now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}
    try:
        async with app.state.pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": _now_iso()}
    except Exception as e:
        return {"ok": False, "ts": _now_iso(), "db": f"{type(e).__name__}: {e}"}

# 业务路由统挂 /v1
app.include_router(meta.router, prefix="/v1", tags=["meta"])
app.include_router(ports.router, prefix="/v1", tags=["ports"])
app.include_router(hs.router,    prefix="/v1", tags=["trade"])
app.include_router(ports_extra.router, prefix="/v1/ports", tags=["ports"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)