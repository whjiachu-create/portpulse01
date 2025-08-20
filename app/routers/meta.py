# app/routers/meta.py
from __future__ import annotations
from typing import List, Dict
from fastapi import APIRouter, Depends, Query
import asyncpg
from app.deps import get_conn, require_api_key

router = APIRouter(tags=["meta"])

@router.get("/sources")
async def list_sources(
    since_hours: int = Query(
        720, ge=0, le=8760, description="hours since last updated (0 = no filter)"
    ),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: None = Depends(require_api_key),
) -> List[Dict]:
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
    # 注意：不在这里释放连接，让 FastAPI 在请求生命周期内托管；或改为 finally: await conn.close()
    return [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat(),
        }
        for r in rows
    ]