# app/deps.py
from __future__ import annotations
from typing import Optional, Annotated
from fastapi import Header

# 说明：
# - 目前不强制校验，仅把 X-API-Key 取出来，供路由使用（与现状兼容）
# - 未来如需强制校验，只需在这里加检查逻辑并抛 HTTPException(401)

def require_api_key(x_api_key: Annotated[Optional[str], Header(None)]) -> Optional[str]:
    """
    返回传入的 X-API-Key；未提供则为 None。
    """
    return x_api_key