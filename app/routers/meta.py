from __future__ import annotations
from fastapi import APIRouter, Response, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import time

from app.dependencies import get_db_pool
from app.models import Source

router = APIRouter(tags=["meta"])

@router.get("/health")
async def health():
    # Railway gate 使用；必须总是 200 且 no-store
    return JSONResponse(content={"ok": True, "ts": time.time()},
                        headers={"Cache-Control": "no-store"})

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
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return sources
