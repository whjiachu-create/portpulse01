# app/routers/ports.py
from fastapi import APIRouter, Depends, Path
from asyncpg.connection import Connection
from asyncpg import UndefinedTableError
from app.deps import get_conn

router = APIRouter()

@router.get("/ports/{unlocode}/snapshot")
async def port_snapshot(
    unlocode: str = Path(..., min_length=3, max_length=5, description="e.g. CNSHA"),
    conn: Connection = Depends(get_conn),
):
    """
    返回最新一条港口快照。
    默认查询表: port_snapshots(unlocode, snapshot_ts, vessels, avg_wait_hours, ...)

    你可以把字段改成自己库里的实际列；只要保持参数化查询和 LIMIT 1 即可。
    """
    try:
        rec = await conn.fetchrow("""
            SELECT unlocode, snapshot_ts, vessels, avg_wait_hours
            FROM port_snapshots
            WHERE unlocode = $1
            ORDER BY snapshot_ts DESC
            LIMIT 1
        """, unlocode.upper())
        if not rec:
            return {"unlocode": unlocode.upper(), "snapshot": None}
        return {
            "unlocode": rec["unlocode"],
            "snapshot_ts": rec["snapshot_ts"],
            "vessels": rec["vessels"],
            "avg_wait_hours": rec["avg_wait_hours"],
        }
    except UndefinedTableError:
        return {"error": "table 'port_snapshots' not found", "unlocode": unlocode.upper()}

@router.get("/ports/{unlocode}/dwell")
async def port_dwell(
    unlocode: str = Path(..., min_length=3, max_length=5),
    conn: Connection = Depends(get_conn),
):
    """
    返回停时（可按天/周聚合）。
    默认查询表: port_dwell(unlocode, date, dwell_hours)

    如需周/月聚合，把 SQL 换成 date_trunc('week'/'month', date) 分组即可。
    """
    try:
        rows = await conn.fetch("""
            SELECT date, dwell_hours
            FROM port_dwell
            WHERE unlocode = $1
            ORDER BY date DESC
            LIMIT 30
        """, unlocode.upper())
        return {
            "unlocode": unlocode.upper(),
            "points": [{"date": r["date"], "dwell_hours": r["dwell_hours"]} for r in rows],
        }
    except UndefinedTableError:
        return {"error": "table 'port_dwell' not found", "unlocode": unlocode.upper()}