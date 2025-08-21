# app/routers/ports.py
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, date

from app.deps import require_api_key, get_conn  # 依赖：鉴权 + asyncpg 连接

router = APIRouter(tags=["ports"])

# =========================
# Pydantic 模型（输出契约）
# =========================

class Snapshot(BaseModel):
    snapshot_ts: datetime
    vessels: int
    avg_wait_hours: float
    congestion_score: float
    src: str
    src_loaded_at: datetime

class SnapshotResponse(BaseModel):
    unlocode: str
    snapshot: Optional[Snapshot] = None  # 无数据时为 null，但永不返回顶层 null

class DwellPoint(BaseModel):
    date: date
    dwell_hours: float
    src: str

class DwellResponse(BaseModel):
    unlocode: str
    points: List[DwellPoint]

class OverviewSource(BaseModel):
    src: str
    src_loaded_at: datetime

class OverviewResponse(BaseModel):
    unlocode: str
    as_of: Optional[datetime] = None
    metrics: Optional[dict] = None
    source: Optional[OverviewSource] = None

class AlertItem(BaseModel):
    unlocode: str
    type: Literal["dwell_change"]
    window_days: int
    latest: float
    baseline: float
    change: float
    note: str

class AlertsResponse(BaseModel):
    unlocode: str
    window_days: int
    alerts: List[AlertItem]

class TrendPoint(BaseModel):
    date: date
    src: str
    vessels: Optional[int] = None
    avg_wait_hours: Optional[float] = None
    congestion_score: Optional[float] = None

class TrendResponse(BaseModel):
    unlocode: str
    days: int
    points: List[TrendPoint]

# =========================
# 辅助函数
# =========================

def _csv_line(values: List[str]) -> str:
    # 简单 CSV（字段都为基础类型 & 无逗号）
    return ",".join(values) + "\n"

# =========================
# 端点：Snapshot（永不顶层 null）
# =========================

@router.get(
    "/{unlocode}/snapshot",
    summary="Port Snapshot",
    tags=["ports"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "unlocode": "USLAX",
                        "snapshot": {
                            "snapshot_ts": "2025-08-14T13:20:02.240670Z",
                            "vessels": 160,
                            "avg_wait_hours": 3.92,
                            "congestion_score": 60.0,
                            "src": "prod",
                            "src_loaded_at": "2025-08-14T13:20:02.240670Z"
                        }
                    }
                }
            }
        }
    },
)
async def port_snapshot(...):
    """
    设计约束：永不返回顶层 null。
    - 若无数据：返回 {"unlocode": <U>, "snapshot": null}
    - 若有数据：返回 {"unlocode": <U>, "snapshot": {...}}
    """
    U = unlocode.upper()
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        U,
    )
    if not row:
        return SnapshotResponse(unlocode=U, snapshot=None)

    snap = Snapshot(
        snapshot_ts=row["snapshot_ts"],
        vessels=int(row["vessels"]),
        avg_wait_hours=float(row["avg_wait_hours"]),
        congestion_score=float(row["congestion_score"]),
        src=row["src"],
        src_loaded_at=row["src_loaded_at"],
    )
    return SnapshotResponse(unlocode=U, snapshot=snap)

# =========================
# 端点：Dwell（永不 500，无数据给空数组）
# =========================

@router.get(
    "/{unlocode}/dwell",
    summary="Port Dwell",
    tags=["ports"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "unlocode": "USLAX",
                        "points": [
                            {"date": "2025-08-07", "dwell_hours": 2.84, "src": "prod"},
                            {"date": "2025-08-08", "dwell_hours": 3.27, "src": "prod"}
                        ]
                    }
                }
            }
        }
    },
)
async def port_dwell(...):

    """
    返回最近 N 天的停时序列（port_dwell）。
    设计目标：永不 500；即使无数据也返回 {"unlocode":..,"points":[]}
    """
    U = unlocode.upper()
    rows = await conn.fetch(
        """
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        U, days,
    )
    points = [
        DwellPoint(date=r["date"], dwell_hours=float(r["dwell_hours"]), src=r["src"])
        for r in rows
    ]
    return DwellResponse(unlocode=U, points=points)

# =========================
# 端点：Overview（json/csv）
# =========================

@router.get(
    "/{unlocode}/overview",
    summary="Port Overview",
    tags=["ports"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "unlocode": "USLAX",
                        "as_of": "2025-08-14T13:20:02.240670Z",
                        "metrics": {
                            "vessels": 160,
                            "avg_wait_hours": 3.92,
                            "congestion_score": 60.0
                        },
                        "source": {"src": "prod", "src_loaded_at": "2025-08-14T13:20:02.240670Z"}
                    }
                }
            }
        }
    },
)
async def port_overview(...):
    
    """
    用最新一条 snapshot 作为该港口的概览。
    - JSON：返回 as_of + metrics + source
    - CSV：返回一行标题 + 一行数据
    """
    U = unlocode.upper()
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        U,
    )

    if format == "csv":
        header = _csv_line(["unlocode", "as_of", "vessels", "avg_wait_hours", "congestion_score"])
        if not row:
            body = _csv_line([U, "", "", "", ""])
        else:
            body = _csv_line([
                U,
                row["snapshot_ts"].isoformat(),
                str(int(row["vessels"])),
                f"{float(row['avg_wait_hours']):.2f}",
                f"{float(row['congestion_score']):.1f}",
            ])
        return PlainTextResponse(
            content=header + body,
            media_type="text/csv; charset=utf-8",
        )

    # JSON
    if not row:
        return OverviewResponse(unlocode=U, as_of=None, metrics=None, source=None)

    return OverviewResponse(
        unlocode=U,
        as_of=row["snapshot_ts"],
        metrics={
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
        },
        source=OverviewSource(
            src=row["src"],
            src_loaded_at=row["src_loaded_at"],
        ),
    )

# =========================
# 端点：Alerts（基于 dwell 的窗口对比）
# =========================

@router.get(
    "/{unlocode}/alerts",
    summary="Port Alerts",
    tags=["ports"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "unlocode": "USNYC",
                        "window_days": 14,
                        "alerts": [
                            {
                                "unlocode": "USNYC",
                                "type": "dwell_change",
                                "window_days": 14,
                                "latest": 2.58,
                                "baseline": 3.12,
                                "change": -0.54,
                                "note": "Δ = latest - baseline（前半窗口均值 vs 后半窗口均值）"
                            }
                        ]
                    }
                }
            }
        }
    },
)
async def port_alerts(...):
    
    """
    简化实现：把 window 解析为天数 N，取最近 N 天 dwell：
    - baseline = 前半窗口均值
    - latest   = 后半窗口均值
    - change   = latest - baseline
    若样本不足，返回空 alerts。
    """
    U = unlocode.upper()

    # 解析 "14d" -> 14
    try:
        days = int(window.rstrip("dD"))
    except Exception:
        raise HTTPException(status_code=422, detail="window must like '14d'")

    rows = await conn.fetch(
        """
        SELECT date, dwell_hours
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        U, days,
    )
    vals = [float(r["dwell_hours"]) for r in rows]
    if len(vals) < 2:
        return AlertsResponse(unlocode=U, window_days=days, alerts=[])

    mid = max(1, len(vals) // 2)
    baseline = sum(vals[:mid]) / len(vals[:mid])
    latest = sum(vals[mid:]) / len(vals[mid:])
    change = latest - baseline

    alert = AlertItem(
        unlocode=U,
        type="dwell_change",
        window_days=days,
        latest=round(latest, 2),
        baseline=round(baseline, 2),
        change=round(change, 2),
        note="Δ = latest - baseline（前半窗口均值 vs 后半窗口均值）",
    )
    return AlertsResponse(unlocode=U, window_days=days, alerts=[alert])

# =========================
# 端点：Trend（支持 fields/分页；基于 snapshots 按天聚合）
# =========================

@router.get("/{unlocode}/trend", summary="Port Trend", response_model=TrendResponse)
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365, description="返回最近 N 天"),
    format: Literal["json", "csv"] = "json",
    fields: Optional[str] = Query(None, description="逗号分隔，例：vessels,avg_wait_hours；为空则全部"),
    tz: str = Query("UTC", description="显示时区，仅影响按天分组边界（此处占位）"),
    limit: int = Query(365, ge=1, le=3650),
    offset: int = Query(0, ge=0, le=100000),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    """
    简化：用 port_snapshots 按日期聚合（snapshot_ts::date），取最后 N 天。
    支持 fields = vessels, avg_wait_hours, congestion_score 的任意子集。
    """
    U = unlocode.upper()
    allowed = {"vessels", "avg_wait_hours", "congestion_score"}
    if fields:
        req = [f.strip() for f in fields.split(",") if f.strip()]
        use_fields = [f for f in req if f in allowed]
        if not use_fields:
            use_fields = list(allowed)
    else:
        use_fields = list(allowed)

    # 按日最新一条（简化）
    rows = await conn.fetch(
        f"""
        WITH daily AS (
          SELECT
            (snapshot_ts AT TIME ZONE 'UTC')::date AS d,
            FIRST_VALUE(vessels) OVER w AS vessels,
            FIRST_VALUE(avg_wait_hours) OVER w AS avg_wait_hours,
            FIRST_VALUE(congestion_score) OVER w AS congestion_score,
            FIRST_VALUE(src) OVER w AS src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $2::int)
          WINDOW w AS (PARTITION BY (snapshot_ts AT TIME ZONE 'UTC')::date ORDER BY snapshot_ts DESC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
        )
        SELECT DISTINCT ON (d) d AS date, vessels, avg_wait_hours, congestion_score, src
        FROM daily
        ORDER BY date DESC
        LIMIT $3 OFFSET $4
        """,
        U, days, limit, offset,
    )

    points = []
    for r in sorted(rows, key=lambda x: x["date"]):
        p = TrendPoint(
            date=r["date"],
            src=r["src"],
            vessels=int(r["vessels"]) if "vessels" in use_fields and r["vessels"] is not None else None,
            avg_wait_hours=float(r["avg_wait_hours"]) if "avg_wait_hours" in use_fields and r["avg_wait_hours"] is not None else None,
            congestion_score=float(r["congestion_score"]) if "congestion_score" in use_fields and r["congestion_score"] is not None else None,
        )
        points.append(p)

    if format == "csv":
        header = ["date"] + use_fields + ["src"]
        buf = _csv_line(header)
        for p in points:
            vals = [p.date.isoformat()]
            for f in use_fields:
                v = getattr(p, f)
                vals.append("" if v is None else str(v))
            vals.append(p.src)
            buf += _csv_line(vals)
        return PlainTextResponse(content=buf, media_type="text/csv; charset=utf-8")

    return TrendResponse(unlocode=U, days=days, points=points)