# app/routers/meta.py
from __future__ import annotations

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from app.deps import get_conn, require_api_key  # 复用连接 & API Key 依赖

router = APIRouter(tags=["meta"])

@router.get("/sources")
async def list_sources(
    conn: asyncpg.Connection = Depends(get_conn),
    auth: None = Depends(require_api_key),
) -> List[Dict[str, Any]]:
    """
    返回数据来源清单：
    [
      { "id": 1, "name": "...", "url": "...", "last_updated": "ISO8601" },
      ...
    ]
    """
    rows = await conn.fetch(
        """
        SELECT id, name, url, last_updated
        FROM sources
        ORDER BY id ASC
        """
    )
    # 容错：列可能允许 NULL，统一转 ISO 字符串
    out: List[Dict[str, Any]] = []
    for r in rows:
        lu = r["last_updated"]
        out.append({
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": lu.isoformat() if lu is not None else None,
        })
    return out