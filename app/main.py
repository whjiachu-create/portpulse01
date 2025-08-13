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

import os
from fastapi import Depends, Header, HTTPException, status

API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}

async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")):
    if not API_KEYS:  # 未配置 API_KEYS 就直接放行（按需）
        return
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
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
    # ==== Business routers mounting (paste into app/main.py) ====
from fastapi import Depends
import importlib

# 你前面已添加过的 API Key 依赖（如果还没有，就把 require_api_key 一起贴上）
# from fastapi import Header, HTTPException, status
# import os
# API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
# async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")):
#     if not API_KEYS:
#         return
#     if not x_api_key or x_api_key not in API_KEYS:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

def _load_router(*module_names: str):
    """按给定模块名顺序尝试导入，成功则返回该模块的 router 变量。"""
    for name in module_names:
        try:
            mod = importlib.import_module(name)
            r = getattr(mod, "router", None)
            if r is not None:
                return r
        except ModuleNotFoundError:
            continue
    return None

# 尝试从 app/routes 或 app/routers 里加载你之前的三个路由模块
meta_router  = _load_router("app.routes.meta",  "app.routers.meta")
ports_router = _load_router("app.routes.ports", "app.routers.ports")
hs_router    = _load_router("app.routes.hs",    "app.routers.hs", "app.routes.trade", "app.routers.trade")

# 逐个挂载（没找到的会跳过，不影响启动）
for r, tag in [(meta_router, "meta"), (ports_router, "ports"), (hs_router, "trade")]:
    if r:
        app.include_router(r, prefix="/v1", tags=[tag], dependencies=[Depends(require_api_key)])
# ==== end ====