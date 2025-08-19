# app/deps.py
from __future__ import annotations
import os, asyncio, contextvars
from typing import AsyncGenerator, Optional, Set
from fastapi import Depends, Header, HTTPException, status
import asyncpg

# —— 读取 API Key 白名单（逗号或空格分隔）——
_KEYS_RAW = os.getenv("API_KEYS", "dev_key_123")
_API_KEYS: Set[str] = {k.strip() for k in _KEYS_RAW.replace(" ", ",").split(",") if k.strip()}

# —— 从 app.state 里取连接池 —— 
async def get_conn(request) -> AsyncGenerator[asyncpg.Connection, None]:
    pool: Optional[asyncpg.pool.Pool] = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    async with pool.acquire() as conn:
        yield conn

# —— 统一鉴权：X-API-Key —— 
async def require_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key not in _API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return True