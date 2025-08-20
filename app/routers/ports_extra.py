# app/routers/ports_extra.py
from __future__ import annotations

from typing import Literal, Optional, List, Set
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
import asyncpg

from app.deps import get_conn, require_api_key

router = APIRouter()

# -----------------------------
# Port Overview（最新单行）
# -----------------------------
@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth = Depends(require_api_key),
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
            f"{unlocode},{snap['snapshot_ts'].isoformat()},"
            f"{int(snap['vessels'])},{float(snap['avg_wait_hours'])},"
            f"{float(snap['congestion_score'])}"
        )
        return PlainTextResponse(
            header + "\n" + line + "\n",
            media_type="text/csv; charset=utf-8",
        )

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
# Port Alerts（极简示例）
# -----------------------------
@router.get("/{unlocode}/alerts", summary="Port Alerts")
async def port_alerts(
    unlocode: str,
    window: str = "14d",
    conn: asyncpg.Connection = Depends(get_conn),
    _auth = Depends(require_api_key),
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
        unlocode, days,
    )

    alerts = []
    if recs:
        latest = float(recs[-1]["dwell_hours"])
        half = max(1, len(recs) // 2)
        baseline = sum(float(r["dwell_hours"]) for r in recs[:half]) / half
        change = latest - baseline
        alerts.append({
            "unlocode": unlocode,
            "type": "dwell_change",
            "window_days": days,
            "latest": round(latest, 2),
            "baseline": round(baseline, 2),
            "change": round(change, 2),
            "note": "Δ = latest - baseline (前半窗口均值)"
        })

    return {"unlocode": unlocode, "window_days": days, "alerts": alerts}

# -----------------------------
# Port Trend（多天导出 / JSON+CSV）
# 新增：fields(字段筛选)、tz(显示时区)、limit/offset(分页)
# -----------------------------
_ALLOWED_FIELDS: Set[str] = {"vessels", "avg_wait_hours", "congestion_score", "src"}

@router.get("/{unlocode}/trend")
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    fields: Optional[str] = Query(
        None,
        description="逗号分隔，例：vessels,avg_wait_hours；为空则返回全部"
    ),
    tz: str = Query("UTC", description="显示时区，仅影响按天分组的边界"),
    limit: int = Query(365, ge=1, le=3650),
    offset: int = Query(0, ge=0, le=100000),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth = Depends(require_api_key),
):
    # 解析字段
    if fields:
        req = [f.strip() for f in fields.split(",") if f.strip()]
        bad = [f for f in req if f not in _ALLOWED_FIELDS]
        if bad:
            raise HTTPException(status_code=400, detail=f"unknown fields: {','.join(bad)}")
        use_fields = req
    else:
        use_fields = ["vessels", "avg_wait_hours", "congestion_score", "src"]

    # 提前拼装选择列（CSV/JSON复用）
    select_cols = ", ".join(use_fields)

    rows = await conn.fetch(
        f"""
        WITH s AS (
          SELECT
            DATE_TRUNC('day', snapshot_ts AT TIME ZONE $2) AS d,
            snapshot_ts, vessels, avg_wait_hours, congestion_score, src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $3::int)
        ),
        r AS (
          SELECT *,
                 ROW_NUMBER() OVER (PARTITION BY d ORDER BY snapshot_ts DESC) AS rn
          FROM s
        )
        SELECT d::date AS date, {select_cols}
        FROM r
        WHERE rn = 1
        ORDER BY date ASC
        OFFSET $4 LIMIT $5
        """,
        unlocode, tz, days, offset, limit,
    )

    if format == "csv":
        header = ",".join(["date"] + use_fields)
        buf = [header]
        for r in rows:
            parts: List[str] = [str(r["date"])]
            for f in use_fields:
                v = r[f]
                parts.append(str(int(v)) if isinstance(v, int) else str(float(v)) if isinstance(v, float) else str(v))
            buf.append(",".join(parts))
        return PlainTextResponse("\n".join(buf) + "\n", media_type="text/csv; charset=utf-8")

    # JSON
    points = []
    for r in rows:
        item = {"date": r["date"].isoformat()}
        for f in use_fields:
            v = r[f]
            if isinstance(v, int):
                item[f] = int(v)
            elif isinstance(v, float):
                item[f] = float(v)
            else:
                item[f] = v
        points.append(item)

    return {"unlocode": unlocode, "days": days, "tz": tz, "limit": limit, "offset": offset, "fields": use_fields, "points": points}