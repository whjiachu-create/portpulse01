# app/routers/ports_extra.py
from __future__ import annotations
from typing import Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
import asyncpg

from app.deps import get_conn, require_api_key

router = APIRouter()

# -----------------------------
# Port Overview（JSON + CSV）
# -----------------------------
@router.get("/{unlocode}/overview", tags=["ports"])
async def port_overview(
    unlocode: str,
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: bool = Depends(require_api_key),
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

    if format == "csv":
        header = "unlocode,as_of,vessels,avg_wait_hours,congestion_score,src"
        data = f"{unlocode},{row['snapshot_ts'].isoformat()},{int(row['vessels'])},{float(row['avg_wait_hours'])},{float(row['congestion_score'])},{row['src']}"
        resp = PlainTextResponse("\n".join([header, data]) + "\n", media_type="text/csv; charset=utf-8")
        # 提示浏览器下载（不强制）
        resp.headers["Content-Disposition"] = f'inline; filename="{unlocode}_overview.csv"'
        return resp

    return {
        "unlocode": unlocode,
        "as_of": row["snapshot_ts"].isoformat(),
        "metrics": {
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
        },
        "source": {"src": row["src"], "src_loaded_at": row["snapshot_ts"].isoformat()},
    }

# -----------------------------
# Port Trend：fields/tz/分页 + CSV
# -----------------------------
_ALLOWED_FIELDS = ["vessels", "avg_wait_hours", "congestion_score", "src"]

@router.get("/{unlocode}/trend", tags=["ports"])
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365),
    fields: str = Query("vessels,avg_wait_hours,congestion_score,src"),
    tz: str = Query("UTC", description="IANA 时区，如 America/Los_Angeles"),
    page: int = Query(1, ge=1),
    limit: int = Query(90, ge=10, le=365),
    format: Literal["json", "csv"] = Query("json"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: bool = Depends(require_api_key),
):
    # 解析字段
    flds = [f.strip() for f in fields.split(",") if f.strip() in _ALLOWED_FIELDS]
    if not flds:
        raise HTTPException(status_code=400, detail="fields param invalid")

    offset = (page - 1) * limit

    rows = await conn.fetch(
        f"""
        WITH s AS (
          SELECT
            (snapshot_ts AT TIME ZONE $2) AS ts_local,
            DATE_TRUNC('day', snapshot_ts AT TIME ZONE $2)::date AS d,
            vessels, avg_wait_hours, congestion_score, src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $3::int)
        ),
        r AS (
          SELECT *,
                 ROW_NUMBER() OVER (PARTITION BY d ORDER BY ts_local DESC) AS rn
          FROM s
        )
        SELECT d, {", ".join(flds)}
        FROM r
        WHERE rn = 1
        ORDER BY d ASC
        OFFSET $4 LIMIT $5
        """,
        unlocode, tz, days, offset, limit
    )

    if format == "csv":
        header = ",".join(["date"] + flds)
        lines = [header]
        for r in rows:
            vals = [r["d"].isoformat()]
            for f in flds:
                v = r[f]
                if isinstance(v, (int, float)):
                    vals.append(str(float(v)) if isinstance(v, float) else str(int(v)))
                else:
                    vals.append(str(v))
            lines.append(",".join(vals))
        resp = PlainTextResponse("\n".join(lines) + "\n", media_type="text/csv; charset=utf-8")
        resp.headers["Content-Disposition"] = f'inline; filename="{unlocode}_trend.csv"'
        return resp

    points = []
    for r in rows:
        item = {"date": r["d"].isoformat()}
        for f in flds:
            item[f] = r[f] if not isinstance(r[f], float) else float(r[f])
        points.append(item)
    return {"unlocode": unlocode, "days": days, "tz": tz, "page": page, "limit": limit, "fields": flds, "points": points}

# -----------------------------
# Alerts：分位阈值 + 变点解释
# -----------------------------
@router.get("/{unlocode}/alerts", tags=["ports"])
async def port_alerts(
    unlocode: str,
    window: int = Query(14, ge=7, le=90),
    pctl: float = Query(0.75, ge=0.5, le=0.95, description="阈值分位数，比如0.75"),
    conn: asyncpg.Connection = Depends(get_conn),
    _auth: bool = Depends(require_api_key),
):
    recs = await conn.fetch(
        """
        SELECT date, dwell_hours
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        unlocode, window
    )
    alerts = []
    if recs:
        ys = [float(r["dwell_hours"]) for r in recs]
        latest = ys[-1]
        base = sorted(ys)  # 分位
        idx = int(max(0, min(len(base)-1, round((len(base)-1)*pctl))))
        thresh = base[idx]
        change = latest - (sum(ys[:-1]) / max(1, len(ys)-1))
        severity = "low"
        if abs(change) > 0.5 and abs(change)/max(0.1, thresh) > 0.15:
            severity = "medium"
        if abs(change) > 1.0 and abs(change)/max(0.1, thresh) > 0.3:
            severity = "high"
        alerts.append({
            "unlocode": unlocode,
            "type": "dwell_change",
            "window_days": window,
            "latest": round(latest, 2),
            "threshold": round(thresh, 2),
            "change": round(change, 2),
            "severity": severity,
            "why": f"latest vs mean(window-1), threshold={int(pctl*100)}p",
        })
    return {"unlocode": unlocode, "window_days": window, "alerts": alerts}