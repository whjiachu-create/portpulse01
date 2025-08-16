from app.deps import get_conn
from fastapi import APIRouter, Depends, Path, Query
from asyncpg.connection import Connection
from app.deps import get_conn

from fastapi import APIRouter, HTTPException, Depends   # ← 加上 Depends
from app.deps import get_conn, require_api_key          # ← 新增这一行
router = APIRouter(prefix="/ports", tags=["ports"])

@router.get("/{unlocode}/snapshot")
async def port_snapshot(
    unlocode: str,
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    返回该港口最近一条快照（port_snapshots）。
    """
    rec = await conn.fetchrow("""
        SELECT unlocode, snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1;
    """, unlocode.upper())

    if not rec:
        return {
            "unlocode": unlocode.upper(),
            "snapshot": None
        }

    return {
        "unlocode": rec["unlocode"],
        "snapshot": {
            "snapshot_ts": rec["snapshot_ts"].isoformat() if rec["snapshot_ts"] else None,
            "vessels": rec["vessels"],
            "avg_wait_hours": float(rec["avg_wait_hours"]) if rec["avg_wait_hours"] is not None else None,
            "congestion_score": float(rec["congestion_score"]) if rec["congestion_score"] is not None else None,
            "src": rec["src"],
            "src_loaded_at": rec["src_loaded_at"].isoformat() if rec["src_loaded_at"] else None,
        }
    }

@router.get("/{unlocode}/dwell")
async def port_dwell(
    unlocode: str,
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    返回最近 N 天的停时序列（port_dwell）。
    """
    rows = await conn.fetch("""
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1
        ORDER BY date DESC
        LIMIT $2;
    """, unlocode.upper(), days)

    # 逆序为按时间升序（便于前端直接画图）
    data = [
        {
            "date": r["date"].isoformat(),
            "dwell_hours": float(r["dwell_hours"]) if r["dwell_hours"] is not None else None,
            "src": r["src"],
        }
        for r in reversed(rows)
    ]
    return {"unlocode": unlocode.upper(), "points": data}