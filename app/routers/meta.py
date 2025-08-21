# app/routers/meta.py
from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from app.deps import get_conn, require_api_key

router = APIRouter()

@router.get(
    "/sources",
    summary="List Sources",
    tags=["meta"],
)
async def list_sources(
    since_hours: int = Query(720, ge=0, le=8760, description="hours since last updated (0 = no filter)"),
    _auth: None = Depends(require_api_key),
    conn: Any = Depends(get_conn),
) -> List[Dict]:
    if since_hours == 0:
        rows = await conn.fetch(
            "SELECT id, name, url, last_updated FROM public.sources ORDER BY id;"
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