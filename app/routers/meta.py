from app.deps import get_conn
from fastapi import APIRouter, Depends
from fastapi import APIRouter, HTTPException, Depends   # ← 加上 Depends
from app.deps import get_conn, require_api_key          # ← 新增这一行
from asyncpg.connection import Connection
from app.deps import get_conn

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/sources")
async def meta_sources(
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    读取 meta_sources 列表（id, name, url, last_updated）。
    """
    rows = await conn.fetch("""
        SELECT id, name, url, last_updated
        FROM meta_sources
        ORDER BY name ASC;
    """)
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
        }
        for r in rows
    ]