# app/routers/ports_extra.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.deps import get_conn

router = APIRouter(prefix="/ports", tags=["ports+"])

def _parse_window(win: str) -> int:
    try:
        if win.endswith("d"):
            return max(1, int(win[:-1]))
        return max(1, int(win))
    except Exception:
        return 14

@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
):
    snap = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        unlocode,
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"No snapshot for {unlocode}")

    res_json = {
        "unlocode": unlocode,
        "as_of": snap["snapshot_ts"].isoformat(),
        "metrics": {
            "vessels": snap["vessels"],
            "avg_wait_hours": float(snap["avg_wait_hours"]),
            "congestion_score": float(snap["congestion_score"]),
        },
        "source": {
            "src": snap["src"],
            "src_loaded_at": snap["src_loaded_at"].isoformat() if snap["src_loaded_at"] else None,
        },
    }

    if format == "json":
        return JSONResponse(content=res_json)

    lines = [
        "metric,value,as_of,src,src_loaded_at",
        f'vessels,{snap["vessels"]},{snap["snapshot_ts"].isoformat()},{snap["src"]},{snap["src_loaded_at"].isoformat() if snap["src_loaded_at"] else ""}',
        f'avg_wait_hours,{float(snap["avg_wait_hours"])},{snap["snapshot_ts"].isoformat()},{snap["src"]},{snap["src_loaded_at"].isoformat() if snap["src_loaded_at"] else ""}',
        f'congestion_score,{float(snap["congestion_score"])},{snap["snapshot_ts"].isoformat()},{snap["src"]},{snap["src_loaded_at"].isoformat() if snap["src_loaded_at"] else ""}',
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.get("/{unlocode}/alerts")
async def port_alerts(
    unlocode: str,
    window: str = Query("14d", description="窗口期，如 7d/14d/30d"),
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
):
    days = _parse_window(window)
    start_day = date.today() - timedelta(days=days - 1)

    dwell = await conn.fetch(
        """
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1 AND date >= $2
        ORDER BY date ASC
        """,
        unlocode,
        start_day,
    )
    if not dwell:
        raise HTTPException(status_code=404, detail=f"No dwell data for {unlocode}")

    values = [float(r["dwell_hours"]) for r in dwell]
    last = values[-1]
    base = (sum(values[:-1]) / max(1, len(values) - 1)) if len(values) >= 2 else values[0]
    change_pct = (last - base) / base * 100 if base else 0.0

    alerts = []
    if abs(change_pct) >= 10:
        alerts.append(
            {
                "unlocode": unlocode,
                "type": "dwell_change",
                "window_days": days,
                "latest": last,
                "baseline": round(base, 2),
                "pct_change": round(change_pct, 2),
                "as_of": dwell[-1]["date"].isoformat(),
                "src": dwell[-1]["src"],
            }
        )

    if format == "json":
        return {"unlocode": unlocode, "window_days": days, "alerts": alerts}

    lines = ["unlocode,type,window_days,latest,baseline,pct_change,as_of,src"]
    if alerts:
        a = alerts[0]
        lines.append(
            f'{a["unlocode"]},{a["type"]},{a["window_days"]},{a["latest"]},{a["baseline"]},{a["pct_change"]},{a["as_of"]},{a["src"]}'
        )
    return PlainTextResponse("\n".join(lines), media_type="text/csv")