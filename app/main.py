# app/main.py
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from asyncpg import UndefinedTableError, UndefinedColumnError, DataError

# 业务子路由
from app.routers import meta, ports, hs, ports_extra  # 确保这些模块存在
# 依赖（API Key 校验、DB 连接）
# 需要已有 app/deps.py，其中包含 get_conn / require_api_key 的实现

# ---------------- Config & Helpers ----------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_dsn(raw: str) -> str:
    # 给 asyncpg 适配 sslmode / connect_timeout
    if "?" in raw:
        base, qs = raw.split("?", 1)
    else:
        base, qs = raw, ""
    params = dict(urllib.parse.parse_qsl(qs, keep_blank_values=True))
    params.setdefault("sslmode", "require")
    params.setdefault("connect_timeout", "10")
    return f"{base}?{urllib.parse.urlencode(params)}"


# ---------------- App ----------------
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    openapi_url="/openapi.json",
)

# OpenAPI 安全方案（只定义一次，避免重复定义导致 schema 异常）
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=getattr(app, "title", "PortPulse API"),
        version=getattr(app, "version", "1.0.0"),
        description="PortPulse & TradeMomentum API",
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {}).update({
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    })
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

# 数据库 DSN
RAW_DSN = os.getenv("DATABASE_URL", "").strip()
DB_DSN: Optional[str] = _normalize_dsn(RAW_DSN) if RAW_DSN else None


# ---------------- DB Pool Lifecycle ----------------
@app.on_event("startup")
async def startup() -> None:
    app.state.pool = None
    app.state.db_error = None

    if not DB_DSN:
        app.state.db_error = "DATABASE_URL is not set"
        return

    try:
        # 兼容 pgbouncer，禁用 prepared statement 的缓存
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
            statement_cache_size=0,
        )
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool is not None:
        await pool.close()


# ---------------- 常见异常到稳定 JSON ----------------
@app.exception_handler(UndefinedTableError)
async def handle_no_table(_, exc: UndefinedTableError):
    return JSONResponse(status_code=424, content={"error": "table_not_found", "detail": str(exc)})

@app.exception_handler(UndefinedColumnError)
async def handle_no_column(_, exc: UndefinedColumnError):
    return JSONResponse(status_code=424, content={"error": "column_not_found", "detail": str(exc)})

@app.exception_handler(DataError)
async def handle_data_error(_, exc: DataError):
    return JSONResponse(status_code=400, content={"error": "bad_input", "detail": str(exc)})


# ---------------- 根路由 & 健康 ----------------
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["meta"])
async def health() -> dict[str, Any]:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": _now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": _now_iso(), "db": None}
    except Exception as e:
        return {"ok": False, "ts": _now_iso(), "db": f"{type(e).__name__}: {e}"}


# ---------------- 业务路由挂载（关键） ----------------
# 注意：prefix 统一放在 include_router，而各子路由文件内部只用自身的相对前缀
# 这样最终路径是 /v1/ports/... /v1/meta/... /v1/hs/...
app.include_router(meta.router,       prefix="/v1")
app.include_router(ports.router,      prefix="/v1")  # ★ 必须：否则 /v1/ports/* 404
app.include_router(ports_extra.router, prefix="/v1")
app.include_router(hs.router,         prefix="/v1")


# 本地调试： uvicorn app.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)