from __future__ import annotations
import os
from typing import AsyncGenerator
from fastapi import Depends, Header, HTTPException, Request

# 说明：
# - 项目中已存在 get_db_pool（meta.py 正在使用），此处直接复用
# - 如果 get_db_pool 不在同文件，请确保从其定义处导入；默认与本文件同名导出
try:
    get_db_pool  # type: ignore[name-defined]
except NameError:
    # 如本地开发环境意外缺失，可给出兜底实现/导入（按项目真实情况处理）
    from .dependencies import get_db_pool  # noqa: F401  # type: ignore

API_KEY = os.getenv("API_KEY", "dev_key_123")

async def require_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")) -> None:
    """
    简单 API Key 校验：
    - 期望请求头 X-API-Key 等于环境变量 API_KEY（默认 dev_key_123）
    - 校验失败返回 401
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

async def get_conn(pool = Depends(get_db_pool)) -> AsyncGenerator:
    """
    基于 asyncpg.Pool 提供连接依赖：
    用法：conn=Depends(get_conn)
    """
    async with pool.acquire() as conn:
        yield conn

__all__ = ["get_db_pool", "require_api_key", "get_conn"]