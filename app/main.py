# app/main.py
import os
import ssl
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _build_ssl() -> ssl.SSLContext:
    """
    Build a strict SSL context for asyncpg.
    Works with Supabase (sslmode=require / verify-ca / verify-full).
    """
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def _normalize_dsn(raw: str) -> str:
    """
    Ensure DATABASE_URL has sslmode=require and a connect timeout,
    and avoid duplicated '?' or sslmode parameters.
    """
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")

    dsn = raw
    # ensure only one '?'
    if dsn.count("?") > 1:
        # take everything before first '?', then merge query params
        base, query = dsn.split("?", 1)
        # remove possible duplicated 'sslmode=' fragments
        parts = [p for p in query.replace("??", "?").split("&") if p]
        # keep only the first sslmode setting if exists
        seen_ssl = False
        cleaned = []
        for p in parts:
            if p.startswith("sslmode="):
                if not seen_ssl:
                    cleaned.append(p)
                    seen_ssl = True
                # else drop duplicates
            else:
                cleaned.append(p)
        dsn = base + "?" + "&".join(cleaned)

    # append sslmode=require if missing
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"

    # append connect_timeout if missing
    if "connect_timeout=" not in dsn:
        dsn += "&connect_timeout=10"

    return dsn

async def _init_conn(conn: asyncpg.Connection) -> None:
    # Keep session in UTC, and set json codec (optional)
    await conn.execute("SET TIME ZONE 'UTC'")
    try:
        await conn.set_type_codec(
            "json",
            encoder=lambda v: json.dumps(v),
            decoder=lambda v: json.loads(v),
            schema="pg_catalog",
        )
    except Exception:
        # ignore if codec already set or extension not needed
        pass

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
)

# CORS (按需调整)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# DB Pool lifecycle
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    dsn_raw = os.getenv("DATABASE_URL", "")
    try:
        dsn = _normalize_dsn(dsn_raw)
        app.state.pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=int(os.getenv("POOL_MIN", "0")),   # 0 可节省空闲实例
            max_size=int(os.getenv("POOL_MAX", "5")),   # Railway 免费/小型套餐足够
            max_inactive_connection_lifetime=60.0,      # 1 分钟回收空闲连接
            command_timeout=30.0,                       # 查询级超时
            init=_init_conn,
            ssl=_build_ssl(),                           # <—— 关键：强制 SSL
        )
        app.state.db_error = None
    except Exception as e:
        app.state.pool = None
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.Pool] = getattr(app.state, "pool", None)
    if pool:
        await pool.close()

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")

@app.get("/v1/health")
async def health() -> Dict[str, Any]:
    """
    Basic liveness + DB connectivity check.
    IMPORTANT: keep SQL in ENGLISH to avoid translation issues.
    """
    pool: Optional[asyncpg.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": utc_now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}

    try:
        async with pool.acquire() as conn:
            ok = await conn.fetchval("SELECT 1;")
        return {"ok": bool(ok == 1), "ts": utc_now_iso(), "db": "ok"}
    except Exception as e:
        return {"ok": False, "ts": utc_now_iso(), "db": f"{type(e).__name__}: {e}"}

# ===== 你其余的业务路由保持原样放在下面 =====
# /v1/meta/sources
# /v1/ports/{unlocode}/snapshot
# /v1/ports/{unlocode}/dwell
# /v1/hs/{code}/imports
# （无需改动）