# app/routers/ports_extra.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends   # ← 加上 Depends
from app.deps import get_conn, require_api_key          # ← 新增这一行 
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
import asyncpg

from app.deps import get_conn  # 复用全局连接池（app/main.py 在 startup 里创建）

router = APIRouter()


# -----------------------------
# Port Overview （已上线的单行总览，保留）
# -----------------------------
@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    format: str = "json",
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    取该港口**最新一次**快照（vessels / avg_wait_hours / congestion_score）
    - JSON：结构化返回（含 as_of 与 source）
    - CSV：单行（header: unlocode,as_of,vessels,avg_wait_hours,congestion_score）
    """
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
        # 单行导出
        row = ",".join(
            [
                "unlocode,as_of,vessels,avg_wait_hours,congestion_score",
                f"{unlocode},{snap['snapshot_ts'].isoformat()},{int(snap['vessels'])},{float(snap['avg_wait_hours'])},{float(snap['congestion_score'])}",
            ]
        )
        # Content-Disposition 由网关/浏览器决定是否下载；这里不强制 attachment
        return PlainTextResponse(
            row.split("\n")[1] + "\n",  # 只返回数据行（header 由 smoke 校验拼过，这里走轻量）
            media_type="text/csv; charset=utf-8",
        )

    # 默认 JSON
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
            # 没有独立载入时间列时，用 snapshot_ts 表示“载入/观测时间”
            "src_loaded_at": snap["snapshot_ts"].isoformat(),
        },
    }


# -----------------------------
# Port Alerts （已上线的告警，保留）
# -----------------------------
@router.get("/{unlocode}/alerts")
async def port_alerts(
    unlocode: str,
    window: str = "14d",
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    简化版告警（示例：dwell 变化）
    返回:
    {
      "unlocode": "...",
      "window_days": 14,
      "alerts": [ { type, latest, baseline, change, ... }, ... ]
    }
    """
    # 解析窗口
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
        # baseline：窗口前半段均值（极简基线）
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
# NEW: Port Trend （多天导出 / JSON+CSV）
# -----------------------------
@router.get("/{unlocode}/trend")
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    以“日”为粒度，抽取每天**最新**一条快照（vessels / avg_wait_hours / congestion_score）
    - JSON：points[ {date, vessels, avg_wait_hours, congestion_score, src} ... ]
    - CSV：header: date,vessels,avg_wait_hours,congestion_score,src
    """
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
        # 头 + 多行
        buf = ["date,vessels,avg_wait_hours,congestion_score,src"]
        for r in rows:
            buf.append(
                f"{r['date']},{int(r['vessels'])},{float(r['avg_wait_hours'])},{float(r['congestion_score'])},{r['src']}"
            )
        return PlainTextResponse("\n".join(buf) + "\n", media_type="text/csv; charset=utf-8")

    # JSON
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