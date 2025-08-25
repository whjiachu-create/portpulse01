import logging
from hashlib import sha256
from typing import List, Optional
from datetime import date, timedelta, datetime, timezone

from fastapi import APIRouter, Query, Response, Request
from app.schemas import (
    TrendPoint, TrendResponse,
    DwellPoint, DwellResponse,
    SnapshotResponse, SnapshotMetrics, SourceInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter()  # 在 main.py 挂到 /v1/ports

# ===== Overview（CSV 强 ETag + 304 + HEAD）=====
def _overview_csv(unlocode: str) -> str:
    return "unlocode,as_of,vessels,avg_wait_hours,congestion_score\n%s,%s,57,26.0,62\n" % (
        unlocode, datetime.now(timezone.utc).date().isoformat()
    )

def _overview_headers(body: str) -> dict:
    return {
        "ETag": '"' + sha256(body.encode()).hexdigest() + '"',
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "overview:strong-etag",
    }

@router.get("/{unlocode}/overview", summary="Port overview (CSV)")
async def get_overview_csv(unlocode: str, request: Request) -> Response:
    body = _overview_csv(unlocode)
    headers = _overview_headers(body)
    inm = request.headers.get("if-none-match", "")
    if headers["ETag"] in inm or f'W/{headers["ETag"]}' in inm:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="text/csv; charset=utf-8", headers=headers)

@router.head("/{unlocode}/overview")
async def head_overview_csv(unlocode: str, request: Request) -> Response:
    body = _overview_csv(unlocode)
    headers = _overview_headers(body)
    inm = request.headers.get("if-none-match", "")
    if headers["ETag"] in inm or f'W/{headers["ETag"]}' in inm:
        return Response(status_code=304, headers=headers)
    return Response(status_code=200, headers=headers)

# ===== Trend（JSON 分页 + CSV 强 ETag）=====
def _demo_trend(unlocode: str, days: int) -> List[TrendPoint]:
    if unlocode not in {"USLAX", "USNYC"}:
        return []
    today = date.today()
    pts: List[TrendPoint] = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        pts.append(TrendPoint(
            date=d,
            vessels=50 + (i % 7),
            avg_wait_hours=24.0 + (i % 5),
            congestion_score=min(100.0, 40.0 + i * 0.2),
            src="DEMO"
        ))
    return pts

@router.get("/{unlocode}/trend", response_model=TrendResponse, summary="Port trend series (json/csv)")
async def get_trend(
    unlocode: str,
    request: Request,
    response: Response,
    days: int = Query(180, ge=1, le=365),
    fields: Optional[str] = Query(None, description="comma-joined: vessels,avg_wait_hours,congestion_score"),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(365, ge=1, le=365),
    offset: int = Query(0, ge=0),
):
    points = _demo_trend(unlocode, days)
    points = points[offset: offset + limit]

    if format == "csv":
        cols = ["vessels", "avg_wait_hours", "congestion_score"]
        if fields:
            picked = [f for f in fields.split(",") if f in cols]
            if picked: cols = picked
        header = ["date"] + cols + ["src"]
        rows = [",".join(header)]
        for p in points:
            line = [p.date.isoformat()] + [
                "" if getattr(p, c) is None else str(getattr(p, c)) for c in cols
            ] + [p.src or ""]
            rows.append(",".join(line))
        body = "\n".join(rows) + "\n"
        etag = '"' + sha256(body.encode("utf-8")).hexdigest() + '"'
        inm = request.headers.get("if-none-match", "")
        if etag in inm or f'W/{etag}' in inm:
            response.headers["Cache-Control"] = "public, max-age=300, no-transform"
            response.headers["ETag"] = etag
            return Response(status_code=304)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Cache-Control": "public, max-age=300, no-transform", "ETag": etag, "Vary": "Accept-Encoding"},
        )

    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return TrendResponse(unlocode=unlocode, points=points)

# ===== Dwell（永不 500；空也 200）=====
@router.get("/{unlocode}/dwell", response_model=DwellResponse, summary="Daily dwell hours")
async def get_dwell(
    unlocode: str,
    response: Response,
    days: int = Query(30, ge=1, le=90),
):
    pts: List[DwellPoint] = []
    if unlocode in {"USLAX", "USNYC"}:
        today = date.today()
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            pts.append(DwellPoint(date=d, dwell_hours=24.0 + (i % 6), src="DEMO"))
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return DwellResponse(unlocode=unlocode, points=pts)

# ===== Snapshot（顶层不为 null；NOPE 也 200）=====
@router.get("/{unlocode}/snapshot", response_model=SnapshotResponse, summary="Latest snapshot for dashboards")
async def get_snapshot(response: Response, unlocode: str):
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    now = datetime.now(timezone.utc)
    if unlocode in {"USLAX", "USNYC"}:
        metrics = SnapshotMetrics(vessels=57, avg_wait_hours=26.0, congestion_score=62.0)
        return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=metrics, source=SourceInfo(src="DEMO"))
    return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=SnapshotMetrics(), source=SourceInfo(src=None))
# HEAD for trend CSV: same headers (ETag/Cache-Control), no body
from fastapi import Response, Request, Query
from typing import Optional
import hashlib
from datetime import date, timedelta

@router.head("/{unlocode}/trend")
async def head_trend(
    unlocode: str,
    request: Request,
    days: int = Query(180, ge=1, le=365),
    fields: Optional[str] = Query(None),
):
    # 复用 get_trend 的生成规则（轻量内联，无需读真实数据）
    cols = ["vessels","avg_wait_hours","congestion_score"]
    if fields:
        pick = [f for f in fields.split(",") if f in cols]
        if pick: cols = pick

    # 小体量占位，确保 ETag 稳定
    today = date.today()
    header = ["date"] + cols + ["src"]
    rows = [",".join(header)]
    for i in range(7):
        d = (today - timedelta(days=6 - i)).isoformat()
        rows.append(",".join([d] + [""]*len(cols) + ["DEMO"]))
    body = "\n".join(rows) + "\n"
    etag = '"' + hashlib.sha256(body.encode("utf-8")).hexdigest() + '"'

    inm = request.headers.get("if-none-match","")
    headers = {
        "Cache-Control": "public, max-age=300, no-transform",
        "ETag": etag,
        "Vary": "Accept-Encoding",
    }
    if etag in inm or f'W/{etag}' in inm:
        return Response(status_code=304, headers=headers)
    return Response(status_code=200, headers=headers)
