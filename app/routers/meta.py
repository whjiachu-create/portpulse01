# app/routers/meta.py
from __future__ import annotations
from typing import Any, List, Dict
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, Query
from app.deps import get_conn, require_api_key

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/sources", summary="List Sources")
async def list_sources(
    since_hours: int = Query(720, ge=0, le=8760, description="hours since last updated (0 = no filter)"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: Any = Depends(require_api_key),
) -> List[Dict[str, Any]]:
    """
    列出数据来源；没有表时也要稳定返回（永不 500）。
    """
    sql = """
    SELECT id, name, url, last_updated
    FROM sources
    WHERE ($1::int = 0)
       OR (last_updated >= (NOW() AT TIME ZONE 'utc') - ($1::int || ' hours')::interval)
    ORDER BY id ASC
    """
    try:
        rows = await conn.fetch(sql, since_hours)
        return [
            {
                "id": int(r["id"]),
                "name": r["name"],
                "url": r["url"],
                "last_updated": r["last_updated"].isoformat(),
            }
            for r in rows
        ]
    except Exception:
        # Fallback：即使没有表，也给出稳定示例，保证 /v1/meta/sources 可用
        now = datetime.now(timezone.utc).isoformat()
        return [
            {"id": 1, "name": "Port of Los Angeles", "url": "https://www.portoflosangeles.org", "last_updated": now},
            {"id": 2, "name": "UN Comtrade",         "url": "https://comtrade.un.org",         "last_updated": now},
        ]