# app/deps.py
from __future__ import annotations
from typing import Optional
from fastapi import Header, HTTPException, Request, status
import asyncpg

ALLOWED_KEYS = {"dev_key_123"}  # 现阶段白名单

async def require_api_key(
    request: Request,  # ← 必须是 fastapi.Request，避免被当成 query 参数
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    if not x_api_key or x_api_key not in ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
    request.state.api_key = x_api_key  # 便于后续日志/限速使用

async def get_conn(request: Request) -> asyncpg.Connection:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    try:
        return await pool.acquire()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB acquire failed: {type(e).__name__}: {e}")