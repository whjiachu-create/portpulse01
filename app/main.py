# app/main.py 仅示意关键段，按你文件结构替换相应位置
import os
import asyncpg
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.cors import CORSMiddleware

from app.routers import ports, ports_extra, meta, hs  # 你的其它路由模块

app = FastAPI()

# 中间件（照你现有的保持即可）
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"], allow_methods=["*"])

@app.on_event("startup")
async def startup():
    app.state.pool = None
    db_dsn = os.getenv("DATABASE_URL")
    if not db_dsn:
        app.state.db_error = "DATABASE_URL not set"
        return
    try:
        app.state.pool = await asyncpg.create_pool(
            dsn=db_dsn,
            min_size=1, max_size=12,
            statement_cache_size=0,         # ← 防止 pgbouncer 冲突
            max_inactive_connection_lifetime=300,
        )
        app.state.db_error = None
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown():
    pool = getattr(app.state, "pool", None)
    if pool:
        await pool.close()

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["meta"])
async def health():
    ok = app.state.pool is not None and app.state.db_error is None
    return {"ok": bool(ok), "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "db": (None if ok else app.state.db_error)}

# 路由挂载（只在这里加前缀）
app.include_router(ports.router,       prefix="/v1/ports", tags=["ports"])
app.include_router(ports_extra.router, prefix="/v1/ports", tags=["ports"])
app.include_router(hs.router,          prefix="/v1",       tags=["trade"])
app.include_router(meta.router,        prefix="/v1/meta",  tags=["meta"])