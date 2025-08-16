# app/routers/ports_extra.py
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
import asyncpg
import datetime as dt

from app.deps import get_conn, require_api_key

# 关键：挂在 /ports，最终路径是 /v1/ports/...
router = APIRouter(prefix="/ports", tags=["ports"])


# ---------------------------------------------------------------------
# /v1/ports/{unlocode}/overview
#   - JSON: 单条最新快照（含 as_of、metrics、source）
#   - CSV : header + 单行（用于客户下载/粘贴）
# ---------------------------------------------------------------------
@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
    auth=Depends(require_api_key),
):
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

    as_of = row["snapshot_ts"].isoformat()
    vessels = int(row["vessels"])
    wait_h = float(row["avg_wait_hours"])
    cong = float(row["congestion_score"])
    src = row["src"]

    if format == "csv":
        header = "unlocode,as_of,vessels,avg_wait_hours,congestion_score"
        line = f"{unlocode},{as_of},{vessels},{wait_h},{cong}"
        # 提示下载（浏览器会弹保存）
        fname = f"overview_{unlocode}_{as_of[:10]}.csv"
        return PlainTextResponse(
            header + "\n" + line + "\n",
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return {
        "unlocode": unlocode,
        "as_of": as_of,
        "metrics": {
            "vessels": vessels,
            "avg_wait_hours": wait_h,
            "congestion_score": cong,
        },
        "source": {
            "src": src,
            "src_loaded_at": as_of,  # 当前表无独立“载入时间”，用 snapshot_ts 代表
        },
    }


# ---------------------------------------------------------------------
# /v1/ports/{unlocode}/alerts
#   - 简化版告警：近 N 天的 dwell 变化（latest vs 前半窗口均值）
# ---------------------------------------------------------------------
@router.get("/{unlocode}/alerts")
async def port_alerts(
    unlocode: str,
    window: str = Query("14d", description="例如 7d / 14d / 30d"),
    conn: asyncpg.Connection = Depends(get_conn),
    auth=Depends(require_api_key),
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
                "note": "Δ = latest - baseline（窗口前半段均值）",
            }
        )

    return {"unlocode": unlocode, "window_days": days, "alerts": alerts}


# ---------------------------------------------------------------------
# /v1/ports/{unlocode}/trend
#   - 多天趋势：按天取“当日最新快照”  (JSON/CSV)
# ---------------------------------------------------------------------
@router.get("/{unlocode}/trend")
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
    auth=Depends(require_api_key),
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
        header = "date,vessels,avg_wait_hours,congestion_score,src"
        lines = [header]
        for r in rows:
            lines.append(
                f"{r['date']},{int(r['vessels'])},{float(r['avg_wait_hours'])},{float(r['congestion_score'])},{r['src']}"
            )
        fname = f"trend_{unlocode}_{dt.date.today().isoformat()}.csv"
        return PlainTextResponse(
            "\n".join(lines) + "\n",
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

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