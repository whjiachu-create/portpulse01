# app/routers/ports.py
from __future__ import annotations

from typing import List, Dict
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_conn, require_api_key

# 重要：这里不要再写 prefix="/ports"
router = APIRouter()


@router.get("/{unlocode}/snapshot", summary="Port Snapshot", tags=["ports"])
async def port_snapshot(
    unlocode: str,
    conn: asyncpg.Connection = Depends(get_conn),
    _auth=Depends(require_api_key),
) -> Dict:
    """
    返回该港口最近一条快照（port_snapshots）
    """
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        unlocode,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No snapshot for this port")

    return {
        "unlocode": unlocode,
        "snapshot": {
            "snapshot_ts": row["snapshot_ts"].isoformat(),
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
            "src": row["src"],
            "src_loaded_at": row["snapshot_ts"].isoformat(),
        },
    }


@router.get("/{unlocode}/dwell", summary="Port Dwell", tags=["ports"])
async def port_dwell(
    unlocode: str,
    days: int = Query(30, ge=1, le=365, description="最近 N 天"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth=Depends(require_api_key),
) -> Dict[str, List[Dict]]:
    """
    返回最近 N 天停时序列（port_dwell）
    """
    rows = await conn.fetch(
        """
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        unlocode, days,
    )
    return {
        "unlocode": unlocode,
        "points": [
            {"date": r["date"].isoformat(), "dwell_hours": float(r["dwell_hours"]), "src": r["src"]}
            for r in rows
        ],
    }