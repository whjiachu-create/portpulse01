# app/main.py
from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware

APP_NAME = "PortPulse & TradeMomentum API"
API_PREFIX = "/v1"
DB_DSN = os.getenv("DATABASE_URL", "").strip()

app = FastAPI(title=APP_NAME, version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Helpers ----
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ---- Startup / Shutdown ----
@app.on_event("startup")
async def startup() -> None:
    # 如果没配置数据库，也允许启动（/v1/health 会返回 ok:false）
    if not DB_DSN:
        app.state.pool = None
        app.state.db_error = "DATABASE_URL not set"
        return

    try:
        # 关键点：不传 ssl，上交给 asyncpg 根据 DSN 的 sslmode=require 处理
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
            command_timeout=30,
            max_inactive_connection_lifetime=60,
        )
        app.state.db_error = None
    except Exception as e:
        app.state.pool = None
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool:
        await pool.close()

# ---- Routes ----
@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)

@app.get(f"{API_PREFIX}/health")
async def health() -> Dict[str, Any]:
    """
    Basic liveness + DB connectivity check.
    IMPORTANT: keep SQL in ENGLISH to avoid translation issues.
    """
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": utc_now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}

    try:
        async with pool.acquire() as conn:
            # DON'T translate this SQL
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": utc_now_iso()}
    except Exception as e:
        return {"ok": False, "ts": utc_now_iso(), "db": f"{type(e).__name__}: {e}"}