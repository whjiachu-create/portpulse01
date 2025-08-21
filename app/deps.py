# app/deps.py
from __future__ import annotations
import os
from typing import AsyncIterator, Optional, Any
from fastapi import Header, HTTPException, Request

# --- API Key 依赖：兼容 API_KEY / PORTPULSE_API_KEY ---
def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    expected = os.getenv("API_KEY") or os.getenv("PORTPULSE_API_KEY")
    if not expected:
        # 未配置密钥则不强制（CI/本地便于调试）
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")

# --- DB 连接依赖：无池时提供 NoopConn，保证“永不 500” ---
class NoopConn:
    async def fetch(self, *args, **kwargs):  # 查询返回空集
        return []
    async def fetchval(self, *args, **kwargs):  # 单值查询返回 None/1 自行扩展
        return None

async def get_conn(request: Request) -> AsyncIterator[Any]:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        # 无数据库也能跑
        yield NoopConn()
        return
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)