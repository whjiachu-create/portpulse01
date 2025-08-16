# app/routers/ports_extra.py
from __future__ import annotations

from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.deps import get_conn, require_api_key

router = APIRouter()


# ----------------------------------------------------------------------
# Port Overview：最新一次快照（JSON/CSV）
# ----------------------------------------------------------------------
@router.get("/{unlocode}/overview", summary="Port Overview (latest)")
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = Query("json", description="返回格式"),
    dl: bool = Query(False, description="CSV 是否强制下载"),
    conn: asyncpg.Connection = Depends(get_conn),
    _: None = Depends(require_api_key),
):
    snap = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        unlocode,
    )
    if not snap:
        raise HTTPException(status_code=404, detail="No snapshot for this port")

    if format == "csv":
        header = "unlocode,as_of,vessels,avg_wait_hours,congestion_score"
        line = (
            f"{unlocode},"
            f"{snap['snapshot_ts'].isoformat()},"
            f"{int(snap['vessels'])},"
            f"{float(snap['avg_wait_hours'])},"
            f"{float(snap['congestion_score'])}"
        )
        resp = PlainTextResponse(
            header + "\n" + line + "\n",
            media_type="text/csv; charset=utf-8",
        )
        if dl:
            resp.headers[
                "Content-Disposition"
            ] = f'attachment; filename="{unlocode}_overview.csv"'
        return resp

    # JSON
    return {
        "unlocode": unlocode,
        "as_of": snap["snapshot_ts"].isoformat(),
        "metrics": {
            "vessels": int(snap["vessels"]),
            "avg_wait_hours": float(snap["avg_wait_hours"]),
            "congestion_score": float(snap["congestion_score"]),
        },
        "source": {
            "src": snap["src"],
            "src_loaded_at": snap["snapshot_ts"].isoformat(),
        },
    }


# ----------------------------------------------------------------------
# Port Alerts：简单告警（窗口均值对比）
# ----------------------------------------------------------------------
@router.get("/{unlocode}/alerts", summary="Port Alerts (window baseline)")
async def port_alerts(
    unlocode: str,
    window: str = Query("14d", description="如 7d/14d/30d"),
    conn: asyncpg.Connection = Depends(get_conn),
    _: None = Depends(require_api_key),
):
    if not window.endswith("d"):
        raise HTTPException(status_code=400, detail="window must end with 'd'")
    try:
        days = int(window[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid window")
    if days <= 0 or days > 365:
        raise HTTPException(status_code=400, detail="window out of range")

    recs = await conn.fetch(
        """
        SELECT date, dwell_hours
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        unlocode,
        days,
    )

    alerts = []
    if recs:
        latest = float(recs[-1]["dwell_hours"])
        half = max(1, len(recs) // 2)
        baseline = sum(float(r["dwell_hours"]) for r in recs[:half]) / half
        change = latest - baseline
        alerts.append(
            {
                "unlocode": unlocode,
                "type": "dwell_change",
                "window_days": days,
                "latest": round(latest, 2),
                "baseline": round(baseline, 2),
                "change": round(change, 2),
                "note": "Δ = latest - baseline (前半窗口均值)",
            }
        )

    return {"unlocode": unlocode, "window_days": days, "alerts": alerts}


# ----------------------------------------------------------------------
# Port Trend：最近 N 天每日最新快照（JSON/CSV）
# ----------------------------------------------------------------------
@router.get("/{unlocode}/trend", summary="Port Trend (daily latest)")
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    dl: bool = Query(False, description="CSV 是否强制下载"),
    conn: asyncpg.Connection = Depends(get_conn),
    _: None = Depends(require_api_key),
):
    rows = await conn.fetch(
        """
        WITH s AS (
          SELECT
            DATE_TRUNC('day', snapshot_ts) AS d,
            snapshot_ts, vessels, avg_wait_hours, congestion_score, src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $2::int)
        ),
        r AS (
          SELECT *,
                 ROW_NUMBER() OVER (PARTITION BY d ORDER BY snapshot_ts DESC) AS rn
          FROM s
        )
        SELECT d::date AS date,
               vessels, avg_wait_hours, congestion_score, src
        FROM r
        WHERE rn = 1
        ORDER BY date ASC
        """,
        unlocode,
        days,
    )

    if format == "csv":
        buf = ["date,vessels,avg_wait_hours,congestion_score,src"]
        for r in rows:
            buf.append(
                f"{r['date']},{int(r['vessels'])},{float(r['avg_wait_hours'])},"
                f"{float(r['congestion_score'])},{r['src']}"
            )
        resp = PlainTextResponse("\n".join(buf) + "\n", media_type="text/csv; charset=utf-8")
        if dl:
            resp.headers[
                "Content-Disposition"
            ] = f'attachment; filename="{unlocode}_trend_{days}d.csv"'
        return resp

    points = [
        {
            "date": r["date"].isoformat(),
            "vessels": int(r["vessels"]),
            "avg_wait_hours": float(r["avg_wait_hours"]),
            "congestion_score": float(r["congestion_score"]),
            "src": r["src"],
        }
        for r in rows
    ]
    return {"unlocode": unlocode, "days": days, "points": points}