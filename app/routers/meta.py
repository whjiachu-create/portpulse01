# app/routers/meta.py
from __future__ import annotations

from typing import List, Dict
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_conn, require_api_key

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/sources")
async def list_sources(
    # 最近多少小时更新；0=不过滤（返回全部）
    since_hours: int = Query(720, ge=0, le=24 * 365, description="hours since last_updated; 0 = no filter"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: None = Depends(require_api_key),  # 仅校验，不占用返回
) -> List[Dict]:
    if since_hours == 0:
        rows = await conn.fetch(
            "SELECT id, name, url, last_updated FROM sources ORDER BY id"
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, name, url, last_updated
            FROM sources
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