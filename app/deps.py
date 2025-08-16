# app/deps.py
from __future__ import annotations
from typing import AsyncGenerator
from fastapi import HTTPException, Request, Depends
import asyncpg
import os

API_KEY = os.getenv("API_KEY", "dev_key_123")  # 你已有的话沿用

def require_api_key(x_api_key: str | None = None):
    # 允许从 Header: X-API-Key 或 query ?api_key= 读取
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Missing or invalid API key")
    return True

async def get_conn(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    只对「获取连接」过程做保护；业务路由里的异常（如 404）不要在这里吞掉。
    """
    pool: asyncpg.Pool | None = getattr(request.app.state, "pool", None)
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not ready")

    try:
        conn = await pool.acquire()
    except Exception as e:
        # 仅在「获取连接」失败时返回 500
        raise HTTPException(status_code=500, detail=f"DB acquire failed: {type(e).__name__}: {e}")

    try:
        yield conn
    finally:
        try:
            await pool.release(conn)
        except Exception:
            pass