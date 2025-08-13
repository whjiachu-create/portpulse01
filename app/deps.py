# app/deps.py
from typing import AsyncIterator
from fastapi import Request, HTTPException
from asyncpg.connection import Connection
from asyncpg.pool import Pool

async def get_conn(request: Request) -> AsyncIterator[Connection]:
    """Yield a pooled DB connection from app.state.pool."""
    pool: Pool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        # 应用刚启动或连接失败时
        raise HTTPException(status_code=503, detail="DB pool not ready")
    async with pool.acquire() as conn:
        yield conn