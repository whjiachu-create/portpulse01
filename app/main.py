# app/main.py
from __future__ import annotations

import os
import ssl
from typing import Any, Dict, Optional

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# ----------------------------------------------------------------------
# 读取环境变量
# ----------------------------------------------------------------------
DB_DSN = os.getenv("DATABASE_URL", "").strip()
API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "dev_key_123").split(",") if k.strip()]

# ----------------------------------------------------------------------
# FastAPI 应用
# ----------------------------------------------------------------------
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 如需限制来源可改成你的域名列表
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# 依赖：API Key 校验（Header: X-API-Key）
# ----------------------------------------------------------------------
async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    # 若未配置 API_KEYS，则不强制校验（开发环境更方便）
    if not API_KEYS:
        return
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

# ----------------------------------------------------------------------
# 启动 / 关闭：初始化/释放数据库连接池
# 说明：你的 Supabase 连接串里已经带 sslmode=require，这里不强制传自定义 ssl_ctx。
# ----------------------------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    app.state.pool = None
    app.state.db_error = None

    if not DB_DSN:
        app.state.db_error = "DATABASE_URL not set"
        return

    try:
        # 如需自定义证书策略，可打开下方几行（一般不需要）
        # ssl_ctx = ssl.create_default_context()
        # ssl_ctx.check_hostname = False
        # ssl_ctx.verify_mode = ssl.CERT_NONE

        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
            command_timeout=30,
            # ssl=ssl_ctx,  # 如果你想强制自定义 SSL，再放开这行
        )
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"
        app.state.pool = None


@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.Pool] = getattr(app.state, "pool", None)
    if pool:
        await pool.close()
        app.state.pool = None

# ----------------------------------------------------------------------
# 工具：获取连接池（给路由里通过 Depends 使用）
# ----------------------------------------------------------------------
async def get_pool() -> asyncpg.Pool:
    pool: Optional[asyncpg.Pool] = getattr(app.state, "pool", None)
    if not pool:
        raise HTTPException(status_code=503, detail=getattr(app.state, "db_error", "DB pool not initialized"))
    return pool

# ----------------------------------------------------------------------
# 恢复业务路由（根据你的项目结构导入）
# 若文件路径不同，请改成你的真实模块路径
# ----------------------------------------------------------------------
try:
    from app.routers.meta import router as meta_router
except Exception:  # 兼容可能的结构差异
    meta_router = None  # type: ignore

try:
    from app.routers.ports import router as ports_router
except Exception:
    ports_router = None  # type: ignore

try:
    from app.routers.trade import router as trade_router
except Exception:
    trade_router = None  # type: ignore

# 统一加上 API Key 依赖（如某些路由无需鉴权，可在对应模块里单独调整）
if meta_router:
    app.include_router(
        meta_router,
        prefix="/v1/meta",
        tags=["meta"],
        dependencies=[Depends(require_api_key)],
    )
if ports_router:
    app.include_router(
        ports_router,
        prefix="/v1/ports",
        tags=["ports"],
        dependencies=[Depends(require_api_key)],
    )
if trade_router:
    # 你的接口是 /v1/hs/{code}/imports，所以这里用 /v1/hs 作为前缀
    app.include_router(
        trade_router,
        prefix="/v1/hs",
        tags=["trade"],
        dependencies=[Depends(require_api_key)],
    )

# ----------------------------------------------------------------------
# 基础路由
# ----------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    # 直接跳 Swagger
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["default"])
async def health() -> Dict[str, Any]:
    """
    存活与DB连通性检查。
    注意：SQL 必须用英文（避免某些运行时翻译导致 SQL 解析问题）
    """
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": ts, "db": getattr(app.state, "db_error", "not-initialized")}

    try:
        async with pool.acquire() as conn:
            ok = await conn.fetchval("SELECT 1;")
            return {"ok": bool(ok == 1), "ts": ts}
    except Exception as e:
        return {"ok": False, "ts": ts, "db": f"{type(e).__name__}: {e}"}