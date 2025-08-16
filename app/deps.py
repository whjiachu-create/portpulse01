# app/deps.py
from __future__ import annotations

import os
from typing import AsyncGenerator

import asyncpg
from fastapi import Header, HTTPException, Request, status


# ---------- 1) API Key 依赖 ----------
# 允许多个 Key：优先读 API_KEYS（逗号分隔），退化到 API_KEY，最后默认 dev_key_123
_allowed = os.getenv("API_KEYS") or os.getenv("API_KEY") or "dev_key_123"
ALLOWED_KEYS = {k.strip() for k in _allowed.split(",") if k.strip()}

async def require_api_key(x_api_key: str | None = Header(None)) -> None:
    """缺少或错误的 Key 时直接 401"""
    if not x_api_key or x_api_key not in ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


# ---------- 2) 数据库连接依赖 ----------
# 不从 app.main 导入 pool（会循环引用）；而是通过 Request 取 app.state.pool
async def get_conn(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    pool: asyncpg.pool.Pool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    try:
        async with pool.acquire() as conn:
            yield conn
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB acquire failed: {type(e).__name__}: {e}",
        ) from e