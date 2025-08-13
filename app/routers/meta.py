# app/routers/meta.py
from fastapi import APIRouter, Depends
from asyncpg.connection import Connection
from asyncpg import UndefinedTableError
from app.deps import get_conn

router = APIRouter()

@router.get("/meta/sources")
async def meta_sources(conn: Connection = Depends(get_conn)):
    """
    返回数据源清单。
    默认查询表: meta_sources(id, name)
    - 如果你的真实表/列不同，改 SQL 即可。
    """
    try:
        rows = await conn.fetch("""
            SELECT id, name
            FROM meta_sources
            ORDER BY name ASC
        """)
        return [{"id": r["id"], "name": r["name"]} for r in rows]
    except UndefinedTableError:
        # 表还没建好时的友好提示
        return {"error": "table 'meta_sources' not found"}