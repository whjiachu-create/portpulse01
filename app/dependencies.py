from __future__ import annotations
import os
from typing import AsyncIterator
from fastapi import Depends, HTTPException, Request
from .services.deps import get_db_pool

__all__ = ["get_db_pool", "get_conn", "require_api_key"]

async def get_conn(pool=Depends(get_db_pool)) -> AsyncIterator:
    async with pool.acquire() as conn:
        yield conn

async def require_api_key(request: Request):
    key = request.headers.get("x-api-key")
    allowed = os.getenv("API_KEY", "dev_key_123")
    if key != allowed:
        raise HTTPException(status_code=401, detail="invalid api key")
    return None