# app/main.py
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# 子路由（已在 app/routers/ 下）
#   meta.py   -> APIRouter(prefix="/meta",  tags=["meta"])
#   ports.py  -> APIRouter(prefix="/ports", tags=["ports"])
#   hs.py     -> APIRouter(prefix="/hs",    tags=["trade"])
from app.routers import meta, ports, hs  # noqa: E402


# ---------------------------------------------------------------------
# Config & Helpers
# ---------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_dsn(raw: str) -> str:
    """
    确保 DATABASE_URL 适配 asyncpg：
      - 如果没带 sslmode，则追加 sslmode=require
      - 如果没带 connect_timeout，则追加 connect_timeout=10
    注意：这里假设你使用的是 Supabase **pooler** (端口 6543)。
    """
    if "?" in raw:
        base, qs = raw.split("?", 1)
    else:
        base, qs = raw, ""

    params = dict(urllib.parse.parse_qsl(qs, keep_blank_values=True))

    # 避免把 verify-ca/verify-full 搞错；没有就默认 require
    params.setdefault("sslmode", "require")
    params.setdefault("connect_timeout", "10")

    return f"{base}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------
# App
# ---------------------------------------------------------------------

app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    openapi_url="/openapi.json",
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
        # 不中断启动，用于 /v1/health 反馈详细错误
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool is not None:
        await pool.close()


# ---------------------------------------------------------------------
# Routes: 根路径 & 健康检查
# ---------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    # 直接跳到 Swagger
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health")
async def health() -> Dict[str, Any]:
    """
    基础存活 & 数据库连通性检查
    重要：SQL 保持英文，避免翻译引起语法问题
    """
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": _now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}

    try:
        async with pool.acquire() as conn:
            # 不要翻译 SELECT
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": _now_iso()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ts": _now_iso(), "db": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------
# 业务路由挂载（父级只挂 /v1，子路由自带 /meta /ports /hs 前缀）
# 这样最终路径就是：
#   /v1/meta/sources
#   /v1/ports/{unlocode}/snapshot
#   /v1/ports/{unlocode}/dwell
#   /v1/hs/{code}/imports
# ---------------------------------------------------------------------

app.include_router(meta.router,  prefix="/v1")
app.include_router(ports.router, prefix="/v1")
app.include_router(hs.router,    prefix="/v1")


# 若需本地调试：`uvicorn app.main:app --reload --port 8000`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)