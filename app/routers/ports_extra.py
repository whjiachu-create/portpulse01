# app/routers/ports_extra.py
from __future__ import annotations
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.deps import get_conn, require_api_key

# 关键：这里必须带 prefix="/ports"
router = APIRouter(prefix="/ports", tags=["ports"])

# -----------------------------
# Port Overview
# -----------------------------
@router.get("/{unlocode}/overview", summary="Port Overview")
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = "json",
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: Any = Depends(require_api_key),
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
        row = f"{unlocode},{snap['snapshot_ts'].isoformat()},{int(snap['vessels'])},{float(snap['avg_wait_hours'])},{float(snap['congestion_score'])}"
        return PlainTextResponse(header + "\n" + row + "\n", media_type="text/csv; charset=utf-8")

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

# -----------------------------
# Port Alerts（简版）
# -----------------------------
@router.get("/{unlocode}/alerts", summary="Port Alerts")
async def port_alerts(
    unlocode: str,
    window: str = "14d",
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: Any = Depends(require_api_key),
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

# -----------------------------
# Port Trend（JSON+CSV）
# -----------------------------
@router.get("/{unlocode}/trend", summary="Port Trend")
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    fields: str | None = Query(None, description="逗号分隔，如 vessels,avg_wait_hours；为空返回全部"),
    tz: str = Query("UTC", description="显示时区，仅影响按天分组边界"),
    limit: int = Query(365, ge=1, le=3650),
    offset: int = Query(0, ge=0, le=100_000),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: Any = Depends(require_api_key),
):
    rows = await conn.fetch(
        """
        WITH s AS (
          SELECT
            (snapshot_ts AT TIME ZONE 'utc') AT TIME ZONE $2 AS local_ts,
            snapshot_ts, vessels, avg_wait_hours, congestion_score, src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $3::int)
        ),
        r AS (
          SELECT DATE_TRUNC('day', local_ts) AS d, *
          FROM s
        ),
        r2 AS (
          SELECT *,
                 ROW_NUMBER() OVER (PARTITION BY d ORDER BY snapshot_ts DESC) AS rn
          FROM r
        )
        SELECT d::date AS date,
               vessels, avg_wait_hours, congestion_score, src
        FROM r2
        WHERE rn = 1
        ORDER BY date ASC
        LIMIT $4 OFFSET $5
        """,
        unlocode, tz, days, limit, offset,
    )

    cols_all = ("vessels", "avg_wait_hours", "congestion_score", "src")
    if fields:
        keep = tuple(x.strip() for x in fields.split(",") if x.strip() in cols_all)
        cols = keep or cols_all
    else:
        cols = cols_all

    if format == "csv":
        header = ",".join(("date",) + cols)
        buf = [header]
        for r in rows:
            line = [r["date"].isoformat()] + [str(r[c]) if c == "src" else str(float(r[c])) if c != "vessels" else str(int(r[c])) for c in cols]
            buf.append(",".join(line))
        return PlainTextResponse("\n".join(buf) + "\n", media_type="text/csv; charset=utf-8")

    # JSON
    points = []
    for r in rows:
        item = {"date": r["date"].isoformat()}
        for c in cols:
            if c == "vessels":
                item[c] = int(r[c])
            elif c in ("avg_wait_hours", "congestion_score"):
                item[c] = float(r[c])
            else:
                item[c] = r[c]
        points.append(item)
    return {"unlocode": unlocode, "days": days, "points": points}