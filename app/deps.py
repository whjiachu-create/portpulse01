# app/deps.py
from __future__ import annotations

from typing import AsyncGenerator
import asyncpg
from fastapi import Request, HTTPException

async def get_conn(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    从 app.state.pool 里借一个连接，路由里用:
        async for conn in get_conn(request): ...
    或者 FastAPI 依赖注入: Depends(get_conn)
    """
    pool: asyncpg.Pool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool is not ready")
    async with pool.acquire() as conn:
        yield conn