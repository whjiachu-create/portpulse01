from typing import AsyncIterator
from fastapi import Request, HTTPException
from asyncpg.connection import Connection
from asyncpg.pool import Pool

async def get_conn(request: Request) -> AsyncIterator[Connection]:
    """
    从 app.state.pool 获取一个 asyncpg 连接，供路由使用。
    如果连接池未就绪，直接返回 503。
    """
    pool: Pool | None = getattr(request.app.state, "pool", None)  # type: ignore
    if pool is None:
        err = getattr(request.app.state, "db_error", "DB pool not initialized")  # type: ignore
        raise HTTPException(status_code=503, detail=str(err))
    async with pool.acquire() as conn:
        yield conn