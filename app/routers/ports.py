from __future__ import annotations

import io
import csv
import logging
from hashlib import sha256
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query, Header

# Auth
from app.services.dependencies import require_api_key

# Schemas (use schemas, not models)
from app.schemas import (
    PortOverview as _PortOverview,
    PortCallExpanded as _PortCallExpanded,
    PortCallProcessed as _PortCallProcessed,
)

# Overrides + window helpers
from app.services.overrides import (
    load_trend_override,
    latest_from_points,
    enforce_window,
)

router = APIRouter(dependencies=[Depends(require_api_key)])
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _demo_trend_points(unlocode: str, window: int) -> List[Dict[str, Any]]:
    """Deterministic demo when DB/override is absent. ETag-stable."""
    today = datetime.utcnow().date()
    w = max(1, min(30, int(window or 7)))
    base_v, base_wait, base_score = 80, 26.0, 52
    out: List[Dict[str, Any]] = []
    for i in range(w):
        d = today - timedelta(days=w - 1 - i)
        out.append(
            {
                "date": d.isoformat(),
                "vessels": base_v + ((i * 3) % 15),
                "avg_wait_hours": round(base_wait + ((i * 1.0) % 8), 1),
                "congestion_score": base_score + ((i * 2) % 10),
                "src": "demo",
                # 固定 00:00:00Z，避免使用“当前时间”导致 ETag 抖动
                "as_of": (f"{d.isoformat()}T00:00:00Z" if i == w - 1 else None),
            }
        )
    return out

def _etag_headers(csv_text: str, source: str) -> Dict[str, str]:
    etag = '"' + sha256(csv_text.encode()).hexdigest() + '"'
    return {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": source,
    }

def _maybe_304(request: Request, headers: Dict[str, str]) -> Optional[Response]:
    inm = request.headers.get("if-none-match")
    if not inm:
        return None
    candidates = [s.strip() for s in inm.split(",")]
    if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
        return Response(status_code=304, headers=headers)
    return None

def _coerce_window(window: Optional[int], days: Optional[int]) -> int:
    """
    Accept both `window` and legacy `days` as synonyms.
    Falls back to 7; clamps to [1, 30] to mirror query validators.
    """
    w = window if window is not None else (days if days is not None else 7)
    # clamp
    if w < 1:
        w = 1
    if w > 30:
        w = 30
    return w

def _select_points(unlocode: str, window: int) -> List[Dict[str, Any]]:
    """Prefer overrides; fall back to demo; enforce window."""
    ov = load_trend_override(unlocode, window) or {}
    pts = (ov.get("points") or []) or _demo_trend_points(unlocode, window)
    payload = enforce_window({"unlocode": unlocode.upper(), "points": pts}, window)
    return payload["points"]

def _trend_csv(points: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "vessels", "avg_wait_hours", "congestion_score", "src", "as_of"])
    for p in points:
        w.writerow([
            p.get("date"),
            p.get("vessels"),
            p.get("avg_wait_hours"),
            p.get("congestion_score"),
            p.get("src"),
            p.get("as_of"),
        ])
    return buf.getvalue()

def _latest_snapshot_flat(unlocode: str) -> Dict[str, Any]:
    """
    Legacy flat snapshot (_PortOverview):
    waiting_vessels <- last.vessels
    avg_wait_hours  <- last.avg_wait_hours
    updated_at      <- last.as_of or `${last.date}T00:00:00Z`
    其它旧字段 P1 允许为空。
    """
    pts = _select_points(unlocode, window=7)
    last = latest_from_points(pts) if pts else None
    return {
        "unlocode": unlocode.upper(),
        "port_name": None,
        "country": None,
        "arrivals_7d": None,
        "departures_7d": None,
        "waiting_vessels": (last or {}).get("vessels"),
        "avg_wait_hours": (last or {}).get("avg_wait_hours"),
        "avg_berth_hours": None,
        "updated_at": (last or {}).get("as_of") or (f"{(last or {}).get('date')}T00:00:00Z" if last else None),
        # 内部用字段（不在响应模型里）
        "_congestion_score": (last or {}).get("congestion_score"),
        "_src": (last or {}).get("src", "demo"),
        "_as_of_date": (last or {}).get("date"),
    }

def _overview_csv_from_snapshot(snap: Dict[str, Any]) -> str:
    # 与历史合同保持一致
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["unlocode", "as_of", "as_of_date", "vessels", "avg_wait_hours", "congestion_score", "src"])
    w.writerow([
        snap.get("unlocode"),
        snap.get("updated_at"),
        snap.get("_as_of_date"),
        snap.get("waiting_vessels"),
        snap.get("avg_wait_hours"),
        snap.get("_congestion_score"),
        snap.get("_src"),
    ])
    return buf.getvalue()

def _parse_date_range(start_date: Optional[str], end_date: Optional[str]) -> Tuple[date, date]:
    try:
        if not start_date and not end_date:
            end_d = datetime.utcnow().date()
            start_d = end_d - timedelta(days=30)
        elif not start_date:
            end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            start_d = end_d - timedelta(days=30)
        elif not end_date:
            start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_d = start_d + timedelta(days=30)
        else:
            start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_d > end_d:
            raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")
        return start_d, end_d
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")

def _validate_pagination(limit: Optional[int], offset: Optional[int]) -> Tuple[int, int]:
    l = 100 if limit is None else limit
    o = 0 if offset is None else offset
    if not (1 <= l <= 1000):
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    if not (0 <= o <= 100000):
        raise HTTPException(status_code=422, detail="offset must be between 0 and 100000")
    return l, o

def _get_port_service():
    try:
        from app.services.deps import PortService  # preferred
        return PortService()
    except Exception:
        try:
            from app.services.dependencies import PortService  # fallback
            return PortService()
        except Exception as e:
            logger.error("PortService import failed: %s", e)
            return None

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@router.get("/{unlocode}/overview")
async def get_overview(
    unlocode: str,
    request: Request,
    format: Optional[str] = Query(None, pattern="^(json|csv)$"),
    accept: Optional[str] = Header(None),
):
    """Overview: default JSON; CSV when `format=csv` or `Accept: text/csv`.
    Keeps strong ETag/304 behavior for CSV.
    """
    snap = _latest_snapshot_flat(unlocode)

    # Decide output format: explicit query param > Accept header > default JSON
    fmt = (format or "").lower()
    if not fmt:
        acc = (accept or "").lower()
        fmt = "csv" if ("text/csv" in acc) else "json"

    if fmt == "json":
        # mirror /snapshot (legacy flat)
        return {k: v for k, v in snap.items() if not k.startswith("_")}

    # CSV + strong ETag + conditional 304
    csv_text = _overview_csv_from_snapshot(snap)
    headers = _etag_headers(csv_text, "ports:overview:strong-etag")
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(content=csv_text.encode(), media_type="text/csv; charset=utf-8", headers=headers)

@router.head("/{unlocode}/overview")
async def head_overview(
    unlocode: str,
    request: Request,
    format: Optional[str] = Query(None, pattern="^(json|csv)$"),
    accept: Optional[str] = Header(None),
):
    csv_text = _overview_csv_from_snapshot(_latest_snapshot_flat(unlocode))
    headers = _etag_headers(csv_text, "ports:overview:strong-etag")
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(status_code=200, headers=headers)

@router.get("/{unlocode}/trend", summary="Port trend (JSON/CSV)")
async def get_trend(
    unlocode: str,
    request: Request,
    window: Optional[int] = Query(None, ge=1, le=30),
    days: Optional[int] = Query(None, ge=1, le=30),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    format: Optional[str] = Query(None, pattern="^(json|csv)$"),
    accept: Optional[str] = Header(None),
):
    # normalize window param (support legacy ?days=)
    w = _coerce_window(window, days)
    points = _select_points(unlocode, w)
    # optional limiting: keep the most recent N points while preserving chronological order
    if limit is not None:
        try:
            n = int(limit)
            if n >= 0:
                points = points[-n:] if n > 0 else []
        except Exception:
            # ignore malformed limit and keep full series
            pass

    # Decide output format: explicit query param > Accept header > default JSON
    fmt = (format or "").lower()
    if not fmt:
        acc = (accept or "").lower()
        fmt = "csv" if ("text/csv" in acc) else "json"

    if fmt == "json":
        return {"unlocode": unlocode.upper(), "points": points}

    csv_text = _trend_csv(points)
    headers = _etag_headers(csv_text, "ports:trend:strong-etag")
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(content=csv_text.encode(), media_type="text/csv; charset=utf-8", headers=headers)

@router.head("/{unlocode}/trend")
async def head_trend(
    unlocode: str,
    request: Request,
    window: Optional[int] = Query(None, ge=1, le=30),
    days: Optional[int] = Query(None, ge=1, le=30),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    format: Optional[str] = Query(None, pattern="^(json|csv)$"),
    accept: Optional[str] = Header(None),
):
    w = _coerce_window(window, days)
    pts = _select_points(unlocode, w)
    if limit is not None:
        try:
            n = int(limit)
            if n >= 0:
                pts = pts[-n:] if n > 0 else []
        except Exception:
            pass
    csv_text = _trend_csv(pts)
    headers = _etag_headers(csv_text, "ports:trend:strong-etag")
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(status_code=200, headers=headers)

@router.get("/{unlocode}/snapshot", response_model=_PortOverview, summary="Port snapshot")
async def snapshot(unlocode: str) -> _PortOverview:
    """Legacy flat snapshot derived from trend (override preferred, fallback demo)."""
    return {k: v for k, v in _latest_snapshot_flat(unlocode).items() if not k.startswith("_")}

# ------------------------------------------------------------------------------
# Calls & Processed
# ------------------------------------------------------------------------------

@router.get("/{unlocode}/calls", response_model=List[_PortCallExpanded], summary="Port Calls", tags=["ports"])
async def port_calls(
    unlocode: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
) -> List[_PortCallExpanded]:
    start_d, end_d = _parse_date_range(start_date, end_date)
    l, o = _validate_pagination(limit, offset)

    svc = _get_port_service()
    if not svc:
        return []

    try:
        data = await svc.get_port_calls_with_pagination(unlocode, start_d, end_d, l, o)
    except Exception as e:
        logger.error("get_port_calls_with_pagination failed for %s: %s", unlocode, e)
        return []

    if not data:
        return []

    return [
        _PortCallExpanded(
            call_id=e.call_id,
            unlocode=e.unlocode,
            vessel_name=e.vessel_name,
            imo=e.imo,
            mmsi=e.mmsi,
            status=e.status,
            eta=e.eta,
            etd=e.etd,
            ata=e.ata,
            atb=e.atb,
            atd=e.atd,
            berth=e.berth,
            terminal=e.terminal,
            last_updated_at=e.last_updated_at,
        )
        for e in data
    ]

@router.get(
    "/{unlocode}/calls/processed",
    response_model=List[_PortCallProcessed],
    summary="Processed Port Calls",
    tags=["ports"],
)
async def processed_port_calls(
    unlocode: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
) -> List[_PortCallProcessed]:
    start_d, end_d = _parse_date_range(start_date, end_date)
    l, o = _validate_pagination(limit, offset)

    svc = _get_port_service()
    if not svc:
        return []

    try:
        data = await svc.get_port_calls_with_pagination(unlocode, start_d, end_d, l, o)
    except Exception as e:
        logger.error("get_port_calls_with_pagination failed for %s: %s", unlocode, e)
        return []

    if not data:
        return []

    result: List[_PortCallProcessed] = []
    for e in data:
        service_time = (e.atd - e.atb).total_seconds() / 3600.0 if e.atb and e.atd else None
        turnaround = (e.atd - e.ata).total_seconds() / 3600.0 if e.ata and e.atd else None
        if e.ata and not e.atb:
            phase = "waiting"
        elif e.atb and not e.atd:
            phase = "berthing"
        elif e.atd:
            phase = "turnaround"
        else:
            phase = None
        wait_hours = (e.atb - e.ata).total_seconds() / 3600.0 if e.ata and e.atb else None

        result.append(
            _PortCallProcessed(
                call_id=e.call_id,
                unlocode=e.unlocode,
                phase=phase,
                wait_hours=wait_hours,
                service_time_hours=service_time,
                turnaround_hours=turnaround,
                updated_at=e.last_updated_at,
            )
        )
    return result
