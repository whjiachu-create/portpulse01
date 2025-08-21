# app/routers/ports_extra.py
from __future__ import annotations
from typing import Any, Literal, Optional

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
@router.get("/{unlocode}/alerts")
async def port_alerts(
    unlocode: str,
    window: str = "14d",
    conn = Depends(get_conn),
    auth = Depends(require_api_key),
):
    # 解析窗口
    if not window.endswith("d"):
        raise HTTPException(status_code=400, detail="window must end with 'd'")
    try:
        days = int(window[:-1])
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid window")
    if days <= 0 or days > 365:
        raise HTTPException(status_code=400, detail="window out of range")

    # 拉取停时
    recs = await conn.fetch(
        """
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        unlocode, days,
    )

    points = [
        {"date": r["date"].isoformat(), "dwell_hours": float(r["dwell_hours"]), "src": r["src"]}
        for r in recs
    ]

    # 复用服务逻辑
    from app.services.alerts import compute_dwell_alert
    alerts = compute_dwell_alert(points)

    return {"unlocode": unlocode, "window_days": days, "alerts": alerts}

# -----------------------------
# Port Trend（JSON+CSV）
# -----------------------------
@router.get("/{unlocode}/trend")
async def port_trend(
    unlocode: str,
    days: int = Query(30, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = Query("json"),
    fields: Optional[str] = Query(None, description="逗号分隔，例：vessels,avg_wait_hours；为空=全部"),
    tz: str = Query("UTC", description="显示时区，仅影响按天分组边界"),
    limit: int = Query(365, ge=1, le=3650),
    offset: int = Query(0, ge=0, le=100000),
    conn: asyncpg.Connection = Depends(get_conn),
    auth = Depends(require_api_key),
):
    """
    以“日”为粒度，抽取每天**最新**一条快照（vessels / avg_wait_hours / congestion_score）
    - 支持 fields、分页 limit/offset
    - 默认 days=30，保证快速返回，避免触发 Cloudflare 524
    """
    want = {"vessels", "avg_wait_hours", "congestion_score"}
    cols = ["vessels", "avg_wait_hours", "congestion_score"]
    if fields:
        fset = {f.strip() for f in fields.split(",") if f.strip()}
        cols = [c for c in ["vessels", "avg_wait_hours", "congestion_score"] if c in fset] or cols
        want = set(cols)

    # 仅选必要列，减少传输
    select_cols = ", ".join(["vessels", "avg_wait_hours", "congestion_score", "src"])

    rows = await conn.fetch(
        """
        WITH s AS (
          SELECT DATE_TRUNC('day', snapshot_ts AT TIME ZONE $3) AS d,
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
        SELECT (d AT TIME ZONE $3)::date AS date, {select_cols}
        FROM r
        WHERE rn = 1
        ORDER BY date ASC
        LIMIT $4 OFFSET $5
        """.format(select_cols=select_cols),
        unlocode, days, tz, limit, offset,
    )

    if format == "csv":
        header = ["date"] + cols + ["src"]
        buf = [",".join(header)]
        for r in rows:
            vals = [r["date"].isoformat()]
            for c in cols:
                vals.append(str(float(r[c]) if c != "vessels" else int(r[c])))
            vals.append(r["src"])
            buf.append(",".join(vals))
        return PlainTextResponse("\n".join(buf) + "\n", media_type="text/csv; charset=utf-8")

    points = []
    for r in rows:
        item = {"date": r["date"].isoformat(), "src": r["src"]}
        if "vessels" in want: item["vessels"] = int(r["vessels"])
        if "avg_wait_hours" in want: item["avg_wait_hours"] = float(r["avg_wait_hours"])
        if "congestion_score" in want: item["congestion_score"] = float(r["congestion_score"])
        points.append(item)

    return {"unlocode": unlocode, "days": days, "points": points}