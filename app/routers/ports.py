# app/routers/ports.py
from __future__ import annotations

from typing import Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_conn, require_api_key

router = APIRouter(prefix="/ports", tags=["ports"])


@router.get("/{unlocode}/snapshot", summary="Port Snapshot")
async def port_snapshot(
    unlocode: str,
    conn: asyncpg.Connection = Depends(get_conn),
    auth=Depends(require_api_key),
):
    """
    返回该港口最近一条快照（port_snapshots）。
    """
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts,
               vessels,
               avg_wait_hours,
               congestion_score,
               src,
               COALESCE(src_loaded_at, snapshot_ts) AS src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1;
        """,
        unlocode,
    )

    if not row:
        return {"unlocode": unlocode, "snapshot": None}

    return {
        "unlocode": unlocode,
        "snapshot": {
            "snapshot_ts": row["snapshot_ts"].isoformat(),
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
            "src": row["src"],
            "src_loaded_at": row["src_loaded_at"].isoformat(),
        },
    }


@router.get("/{unlocode}/dwell", summary="Port Dwell")
async def port_dwell(
    unlocode: str,
    days: int = Query(30, ge=1, le=365, description="返回最近 N 天"),
    conn: asyncpg.Connection = Depends(get_conn),
    auth=Depends(require_api_key),
):
    """
    返回最近 N 天的停时序列（port_dwell）。
    设计目标：永不 500；即使无数据也返回 {"unlocode":..,"points":[]}
    """
    try:
        rows = await conn.fetch(
            """
            SELECT date, dwell_hours, src
            FROM port_dwell
            WHERE unlocode = $1
              AND date >= CURRENT_DATE - $2::int
            ORDER BY date ASC;
            """,
            unlocode,
            days,
        )
    except asyncpg.UndefinedTableError:
        # 由全局异常也会映射，但这里显式返回更清晰
        raise HTTPException(status_code=424, detail="table_not_found: port_dwell")

    # 兜底防脏值/空值，永不抛异常
    points = []
    for r in rows or []:
        raw = r["dwell_hours"]
        try:
            dh = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            dh = None
        points.append(
            {
                "date": r["date"].isoformat(),
                "dwell_hours": dh,
                "src": r["src"],
            }
        )

    return {"unlocode": unlocode, "points": points}