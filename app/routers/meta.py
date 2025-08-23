from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import time
from ..services.deps import get_db_pool

router = APIRouter()

@router.get("/health")
async def health_check():
    return JSONResponse(
        {"ok": True, "ts": time.time()},
        headers={"Cache-Control": "no-store"}
    )

@router.get("/meta/dependencies")
async def list_dependencies(pool=Depends(get_db_pool)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT name FROM dependencies ORDER BY name")
        deps = [row["name"] for row in rows]
        return {"dependencies": deps}