# app/main.py
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from asyncpg import UndefinedTableError, UndefinedColumnError, DataError

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

app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    openapi_url="/openapi.json",
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Operational port metrics and trade flows",
        routes=app.routes,
    )
    comps = schema.setdefault("components", {})
    comps["securitySchemes"] = {
        "APIKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    }
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

RAW_DSN = os.getenv("DATABASE_URL", "").strip()
DB_DSN: Optional[str] = _normalize_dsn(RAW_DSN) if RAW_DSN else None

@app.on_event("startup")
async def startup() -> None:
    app.state.pool = None
    app.state.db_error = None
    if not DB_DSN:
        app.state.db_error = "DATABASE_URL is not set"
        return
    try:
        app.state.pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=5)
    except Exception as e:  # noqa: BLE001
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool is not None:
        await pool.close()

@app.exception_handler(UndefinedTableError)
async def handle_no_table(_, exc: UndefinedTableError):
    return JSONResponse(status_code=424, content={"error": "table_not_found", "detail": str(exc)})

@app.exception_handler(UndefinedColumnError)
async def handle_no_column(_, exc: UndefinedColumnError):
    return JSONResponse(status_code=424, content={"error": "column_not_found", "detail": str(exc)})

@app.exception_handler(DataError)
async def handle_data_error(_, exc: DataError):
    return JSONResponse(status_code=400, content={"error": "bad_input", "detail": str(exc)})

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health")
async def health() -> dict[str, Any]:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": _now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": _now_iso()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ts": _now_iso(), "db": f"{type(e).__name__}: {e}"}

# ---- 挂载业务路由（统一前缀 /v1）----
from app.routers import meta, ports, hs, ports_extra  # noqa: E402

app.include_router(meta.router,  prefix="/v1")
app.include_router(ports.router, prefix="/v1")
app.include_router(hs.router,    prefix="/v1")
app.include_router(ports_extra.router, prefix="/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)