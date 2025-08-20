# app/routers/meta.py
from __future__ import annotations

from typing import Dict, List
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_conn, require_api_key

router = APIRouter(prefix="/v1/meta", tags=["meta"])


@router.get("/sources")
async def list_sources(
    since_hours: int = Query(720, ge=0, le=8760, description="hours since last update"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: None = Depends(require_api_key),  # 只做鉴权，不使用返回值
) -> List[Dict]:
    """
    数据来源列表：
    - `since_hours=0` 返回全部
    - >0 返回最近 N 小时内更新过的来源
    返回字段：id, name, url, last_updated(ISO8601)
    """
    if since_hours == 0:
        rows = await conn.fetch(
            "SELECT id, name, url, last_updated FROM public.sources ORDER BY id"
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, name, url, last_updated
            FROM public.sources
            WHERE last_updated >= now() - ($1::int * interval '1 hour')
            ORDER BY id
            """,
            since_hours,
        )

    return [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat(),
        }
        for r in rows
    ]