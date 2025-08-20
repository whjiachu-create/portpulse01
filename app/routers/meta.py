# app/routers/meta.py
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
import asyncpg

from app.deps import get_conn, require_api_key

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/sources")
async def meta_sources(
    request: Optional[str] = Query(
        None,
        description="Optional echo field from client; kept for backward-compat."
    ),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth = Depends(require_api_key),
):
    """
    返回当前数据源列表及最近载入时间（从 port_snapshots 聚合）。
    响应:
    {
      "sources": [ { "src": "prod", "src_loaded_at": "2025-08-18T..." }, ... ],
      "echo": { "request": "...(可选回显)" }
    }
    """
    rows = await conn.fetch(
        """
        SELECT src, MAX(snapshot_ts) AS src_loaded_at
        FROM port_snapshots
        GROUP BY src
        ORDER BY src
        """
    )
    sources = [
        {"src": r["src"], "src_loaded_at": r["src_loaded_at"].isoformat()}
        for r in rows
    ]
    return {"sources": sources, "echo": {"request": request}}