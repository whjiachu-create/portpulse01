# app/routers/meta.py
from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Response
import json

from app.dependencies import get_db_pool
from app.models import Source

router = APIRouter()

@router.get("/sources", response_model=list[Source])
async def list_sources(response: Response, pool = Depends(get_db_pool)):
    rows = await pool.fetch(
        "SELECT id, name, url, last_updated FROM public.sources ORDER BY id;"
    )
    sources = [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat(),
        }
        for r in rows
    ]
    from fastapi.responses import JSONResponse
    return JSONResponse(sources, headers={"Cache-Control": "public, max-age=300"})