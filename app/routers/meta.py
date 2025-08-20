# app/routers/meta.py
from __future__ import annotations

from typing import List, Dict
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_conn, require_api_key

router = APIRouter()

@router.get("/sources", tags=["meta"])
async def list_sources(
    since_hours: int = Query(
        720, ge=0, le=8760, description="hours since last update"
    ),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: None = Depends(require_api_key),
) -> List[Dict]:
    """
    列出现有数据源；since_hours=0 表示不过滤时间
    返回: [{id, name, url, last_updated}]
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
            WHERE last_updated >= (now() - ($1::int || ' hours')::interval)
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