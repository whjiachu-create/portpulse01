# app/main.py
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from asyncpg import UndefinedTableError, UndefinedColumnError, DataError

# ---- 子路由（每个文件里都有 `router`）----
from app.routers.meta import router as meta_router
from app.routers.ports import router as ports_router
from app.routers.hs import router as hs_router
from app.routers.ports_extra import router as ports_extra_router
from app.routers.deps import api_key_auth  # 统一的 X-API-Key 依赖

# ---------------------------------------------------------------------
# Config & Helpers
# ---------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_dsn(raw: str) -> str:
    """
    确保 DATABASE_URL 适配 asyncpg：
      - 没有 sslmode 则追加 sslmode=require
      - 没有 connect_timeout 则追加 connect_timeout=10
    注：假设使用 Supabase pooler (端口 6543)。
    """
    if "?" in raw:
        base, qs = raw.split("?", 1)
    else:
        base, qs = raw, ""
    params = dict(urllib.parse.parse_qsl(qs, keep_blank_values=True))
    params.setdefault("sslmode", "require")
    params.setdefault("connect_timeout", "10")
    return f"{base}?{urllib.parse.urlencode(params)}"

# ---------------------------------------------------------------------
# App
# ---------------------------------------------------------------------

app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.2",
    openapi_url="/openapi.json",
    docs_url="/docs",
)

# CORS（按需放开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

# 数据库 DSN
RAW_DSN = os.getenv("DATABASE_URL", "").strip()
DB_DSN: Optional[str] = _normalize_dsn(RAW_DSN) if RAW_DSN else None

# ---------------------------------------------------------------------
# Startup / Shutdown: asyncpg 连接池
# ---------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    app.state.pool = None
    app.state.db_error = None
    if not DB_DSN:
        app.state.db_error = "DATABASE_URL is not set"
        return
    try:
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
        )
    except Exception as e:  # noqa: BLE001
        # 不中断启动，让 /v1/health 能暴露错误
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool is not None:
        await pool.close()

# ---------------------------------------------------------------------
# 读库相关常见错误 -> 友好返回
# ---------------------------------------------------------------------

@app.exception_handler(UndefinedTableError)
async def handle_no_table(_, exc: UndefinedTableError):
    return JSONResponse(status_code=424, content={"error": "table_not_found", "detail": str(exc)})

@app.exception_handler(UndefinedColumnError)
async def handle_no_column(_, exc: UndefinedColumnError):
    return JSONResponse(status_code=424, content={"error": "column_not_found", "detail": str(exc)})

@app.exception_handler(DataError)
async def handle_data_error(_, exc: DataError):
    return JSONResponse(status_code=400, content={"error": "bad_input", "detail": str(exc)})

# ---------------------------------------------------------------------
# 根路径 & 健康检查
# ---------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    # 直接跳 Swagger
    return RedirectResponse(url="/docs", status_code=307)

# 健康检查不做鉴权，给 Railway 用
@app.get("/v1/health", tags=["default"])
async def health() -> Dict[str, Any]:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": _now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": _now_iso()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ts": _now_iso(), "db": f"{type(e).__name__}: {e}"}

# ---------------------------------------------------------------------
# 业务路由挂载（父级统一加 /v1，并绑定 API Key 依赖）
#   最终路径：
#     /v1/meta/sources
#     /v1/ports/{unlocode}/snapshot
#     /v1/ports/{unlocode}/dwell
#     /v1/ports/{unlocode}/overview
#     /v1/ports/{unlocode}/alerts
#     /v1/hs/{code}/imports
# ---------------------------------------------------------------------

app.include_router(meta_router,        prefix="/v1", tags=["meta"],  dependencies=[Depends(api_key_auth)])
app.include_router(ports_router,       prefix="/v1", tags=["ports"], dependencies=[Depends(api_key_auth)])
app.include_router(hs_router,          prefix="/v1", tags=["trade"], dependencies=[Depends(api_key_auth)])
app.include_router(ports_extra_router, prefix="/v1", tags=["ports"], dependencies=[Depends(api_key_auth)])

# ---------------------------------------------------------------------
# Swagger 中启用 Authorize 按钮（X-API-Key）
# ---------------------------------------------------------------------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Authenticated by 'X-API-Key' header. Use 'dev_key_123' in dev.",
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["APIKeyHeader"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    # 全局要求鉴权（/v1/health 不受影响，因为路由未加依赖）
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# 若需本地调试：`uvicorn app.main:app --reload --port 8000`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)