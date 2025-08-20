# app/routers/meta.py
from fastapi import APIRouter, Depends
from typing import List, Dict
import asyncpg
from app.deps import get_conn, require_api_key

router = APIRouter()  # ← 不要在这里设置 include_in_schema=False

@router.get("/sources", tags=["meta"], include_in_schema=True)
async def list_sources(
    since_hours: int = 720,
    conn: asyncpg.Connection = Depends(get_conn),
    _auth = Depends(require_api_key),
) -> List[Dict]:
    if since_hours == 0:
        rows = await conn.fetch("SELECT id, name, url, last_updated FROM public.sources ORDER BY id")
    else:
        rows = await conn.fetch("""
            SELECT id, name, url, last_updated
            FROM public.sources
            WHERE last_updated >= now() - ($1::int * interval '1 hour')
            ORDER BY id
        """, since_hours)
    return [
        {"id": int(r["id"]), "name": r["name"], "url": r["url"], "last_updated": r["last_updated"].isoformat()}
        for r in rows
    ]