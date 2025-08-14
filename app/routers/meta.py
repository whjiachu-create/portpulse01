from fastapi import APIRouter, Depends
from asyncpg.connection import Connection
from app.deps import get_conn

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/sources")
async def meta_sources(conn: Connection = Depends(get_conn)):
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