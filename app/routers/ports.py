from __future__ import annotations

import io
import csv
import logging
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING

from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query

# Auth dependency
from app.services.dependencies import require_api_key

# Schemas (use schemas, not models)
from app.schemas import (
    PortOverview as _PortOverview,
    PortCallExpanded as _PortCallExpanded,
    PortCallProcessed as _PortCallProcessed,
)

# Override helpers (file-based overrides + window enforcement)
from app.services.overrides import (
    load_trend_override,
    latest_from_points,
    snapshot_from_override,
    enforce_window,
)

if TYPE_CHECKING:
    from app.schemas import PortOverview, PortCallExpanded, PortCallProcessed

router = APIRouter(dependencies=[Depends(require_api_key)])

logger = logging.getLogger(__name__)


# ----------------------------
# Demo series (deterministic) |
# ----------------------------
def _demo_trend_points(unlocode: str, window: int) -> List[Dict]:
    """
    Deterministic fallback when no DB/override exists.
    Contract-compatible with JSON/CSV/HEAD and strong ETag logic.
    """
    today = datetime.utcnow().date()
    w = max(1, min(30, int(window or 7)))
    base_v, base_wait, base_score = 80, 26.0, 52
    pts: List[Dict] = []
    for i in range(w):
        d = today - timedelta(days=w - 1 - i)
        pts.append(
            {
                "date": d.isoformat(),
                "vessels": base_v + ((i * 3) % 15),
                "avg_wait_hours": round(base_wait + ((i * 1.0) % 8), 1),
                "congestion_score": base_score + ((i * 2) % 10),
                "src": "demo",
                "as_of": None
                if i < w - 1
                else datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            }
        )
    return pts


# ----------------------------
# CSV builders + strong ETag  |
# ----------------------------
def _build_trend_csv_and_headers(unlocode: str, points: List[Dict]) -> Tuple[str, dict]:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["date", "vessels", "avg_wait_hours", "congestion_score", "src", "as_of"])
    for p in points:
        writer.writerow(
            [
                p.get("date"),
                p.get("vessels"),
                p.get("avg_wait_hours"),
                p.get("congestion_score"),
                p.get("src"),
                p.get("as_of"),
            ]
        )
    csv_text = buf.getvalue()
    etag = '"' + sha256(csv_text.encode()).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:trend:strong-etag",
    }
    return csv_text, headers


def _build_overview_csv_and_headers(unlocode: str) -> Tuple[str, dict]:
    """
    Build snapshot CSV (1 row) with strong ETag.
    """
    # Prefer override snapshot; otherwise derive from demo last-point
    snap = snapshot_from_override(unlocode)
    if not isinstance(snap, dict) or not snap.get("metrics"):
        pts = _demo_trend_points(unlocode, 7)
        last = pts[-1] if pts else None
        if last:
            snap = {
                "unlocode": unlocode.upper(),
                "as_of": last.get("as_of"),
                "as_of_date": last.get("date"),
                "metrics": {
                    "vessels": last.get("vessels"),
                    "avg_wait_hours": last.get("avg_wait_hours"),
                    "congestion_score": last.get("congestion_score"),
                },
                "source": {"src": last.get("src", "demo")},
            }
        else:
            snap = {
                "unlocode": unlocode.upper(),
                "as_of": None,
                "as_of_date": None,
                "metrics": {"vessels": None, "avg_wait_hours": None, "congestion_score": None},
                "source": {"src": "demo"},
            }

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["unlocode", "as_of", "as_of_date", "vessels", "avg_wait_hours", "congestion_score", "src"])
    writer.writerow(
        [
            snap.get("unlocode"),
            snap.get("as_of"),
            snap.get("as_of_date"),
            (snap.get("metrics") or {}).get("vessels"),
            (snap.get("metrics") or {}).get("avg_wait_hours"),
            (snap.get("metrics") or {}).get("congestion_score"),
            (snap.get("source") or {}).get("src"),
        ]
    )

    csv_text = buf.getvalue()
    etag = '"' + sha256(csv_text.encode()).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:overview:strong-etag",
    }
    return csv_text, headers


# ----------------------------
# Routes                      |
# ----------------------------
@router.get("/{unlocode}/overview")
async def get_overview_csv(
    unlocode: str,
    request: Request,  # ← moved before defaults
    format: str = Query("csv", pattern="^(json|csv)$"),
):
    # JSON path: mirror /snapshot structure
    if format.lower() == "json":
        snap = snapshot_from_override(unlocode)
        if not isinstance(snap, dict):
            pts = _demo_trend_points(unlocode, 7)
            last = pts[-1] if pts else None
            if last:
                snap = {
                    "unlocode": unlocode.upper(),
                    "as_of": last.get("as_of"),
                    "as_of_date": last.get("date"),
                    "metrics": {
                        "vessels": last.get("vessels"),
                        "avg_wait_hours": last.get("avg_wait_hours"),
                        "congestion_score": last.get("congestion_score"),
                    },
                    "source": {"src": last.get("src", "demo")},
                }
            else:
                snap = {
                    "unlocode": unlocode.upper(),
                    "as_of": None,
                    "as_of_date": None,
                    "metrics": {"vessels": None, "avg_wait_hours": None, "congestion_score": None},
                    "source": {"src": "demo"},
                }
        return snap

    # CSV path with strong ETag & conditional 304
    csv_text, headers = _build_overview_csv_and_headers(unlocode)
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
            return Response(status_code=304, headers=headers)

    return Response(content=csv_text.encode(), media_type="text/csv; charset=utf-8", headers=headers)


@router.head("/{unlocode}/overview")
async def head_overview_csv(
    unlocode: str,
    request: Request,  # ← moved before defaults
    format: str = Query("csv", pattern="^(json|csv)$"),
):
    csv_text, headers = _build_overview_csv_and_headers(unlocode)
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
            return Response(status_code=304, headers=headers)
    return Response(status_code=200, headers=headers)


@router.get("/{unlocode}/trend", summary="Port trend (JSON/CSV)")
async def port_trend(
    unlocode: str,
    request: Request,  # ← moved before defaults
    window: int = Query(7, ge=1, le=30),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    # Prefer override
    ov = load_trend_override(unlocode, window)
    points = (ov or {}).get("points", [])

    # Extra window enforcement
    if window and len(points) > window:
        points = points[-window:]

    # Fallback
    if not points:
        points = _demo_trend_points(unlocode, window)

    if format.lower() == "json":
        payload = {"unlocode": unlocode.upper(), "points": points}
        payload = enforce_window(payload, window)
        return payload

    # CSV
    payload = enforce_window({"unlocode": unlocode.upper(), "points": points}, window)
    csv_text, headers = _build_trend_csv_and_headers(unlocode, payload["points"])
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
            return Response(status_code=304, headers=headers)
    return Response(content=csv_text.encode(), media_type="text/csv; charset=utf-8", headers=headers)


@router.head("/{unlocode}/trend")
async def head_port_trend(
    unlocode: str,
    request: Request,  # ← moved before defaults
    window: int = Query(7, ge=1, le=30),
    format: str = Query("csv", pattern="^(json|csv)$"),
):
    ov = load_trend_override(unlocode, window)
    pts = (ov or {}).get("points", [])
    if not pts:
        pts = _demo_trend_points(unlocode, window)
    payload = enforce_window({"unlocode": unlocode.upper(), "points": pts}, window)
    csv_text, headers = _build_trend_csv_and_headers(unlocode, payload["points"])
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
            return Response(status_code=304, headers=headers)
    return Response(status_code=200, headers=headers)


@router.get("/{unlocode}/snapshot", response_model=_PortOverview, summary="Port snapshot")
async def port_snapshot(unlocode: str) -> Dict[str, Any]:
    """
    Snapshot with robust fallbacks:
    1) override-derived from trend.json
    2) demo last-point if nothing available
    """
    # 1) override
    try:
        ov_snap = snapshot_from_override(unlocode)
        if ov_snap:
            return ov_snap
    except Exception:
        logger.exception("snapshot_from_override failed for %s", unlocode)

    # 2) demo-derived
    pts = _demo_trend_points(unlocode, 7)
    last = pts[-1] if pts else None
    if last:
        return {
            "unlocode": unlocode.upper(),
            "as_of": last.get("as_of"),
            "as_of_date": last.get("date"),
            "metrics": {
                "vessels": last.get("vessels"),
                "avg_wait_hours": last.get("avg_wait_hours"),
                "congestion_score": last.get("congestion_score"),
            },
            "source": {"src": last.get("src", "demo")},
        }

    # hard fallback
    return {
        "unlocode": unlocode.upper(),
        "as_of": None,
        "as_of_date": None,
        "metrics": {"vessels": None, "avg_wait_hours": None, "congestion_score": None},
        "source": {"src": "demo"},
    }


# ----------------------------
# Calls & processed endpoints |
# ----------------------------
@router.get(
    "/{unlocode}/calls",
    response_model=List[_PortCallExpanded],
    summary="Port Calls",
    tags=["ports"],
)
async def port_calls(
    unlocode: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
) -> List[_PortCallExpanded]:
    """
    Detailed port calls with pagination. Returns [] on errors.
    """
    # Parse dates
    try:
        if not start_date and not end_date:
            end_date_obj = datetime.utcnow().date()
            start_date_obj = end_date_obj - timedelta(days=30)
        elif not start_date and end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            start_date_obj = end_date_obj - timedelta(days=30)
        elif start_date and not end_date:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = start_date_obj + timedelta(days=30)
        else:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")

    # Validate pagination
    limit = 100 if limit is None else limit
    offset = 0 if offset is None else offset
    if not (1 <= limit <= 1000):
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    if not (0 <= offset <= 100000):
        raise HTTPException(status_code=422, detail="offset must be between 0 and 100000")

    # Import service
    try:
        from app.services.deps import PortService  # preferred
    except Exception:
        try:
            from app.services.dependencies import PortService  # fallback
        except Exception as _e:
            logger.error("PortService import failed: %s", _e)
            return []

    svc = PortService()
    try:
        data = await svc.get_port_calls_with_pagination(unlocode, start_date_obj, end_date_obj, limit, offset)
    except Exception as e:
        logger.error("get_port_calls_with_pagination failed for %s: %s", unlocode, e)
        return []

    if not data:
        return []

    return [
        _PortCallExpanded(
            call_id=entry.call_id,
            unlocode=entry.unlocode,
            vessel_name=entry.vessel_name,
            imo=entry.imo,
            mmsi=entry.mmsi,
            status=entry.status,
            eta=entry.eta,
            etd=entry.etd,
            ata=entry.ata,
            atb=entry.atb,
            atd=entry.atd,
            berth=entry.berth,
            terminal=entry.terminal,
            last_updated_at=entry.last_updated_at,
        )
        for entry in data
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
    """
    Processed port calls with derived metrics. Returns [] on errors.
    """
    # Parse dates
    try:
        if not start_date and not end_date:
            end_date_obj = datetime.utcnow().date()
            start_date_obj = end_date_obj - timedelta(days=30)
        elif not start_date and end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            start_date_obj = end_date_obj - timedelta(days=30)
        elif start_date and not end_date:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = start_date_obj + timedelta(days=30)
        else:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")

    # Validate pagination
    limit = 100 if limit is None else limit
    offset = 0 if offset is None else offset
    if not (1 <= limit <= 1000):
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    if not (0 <= offset <= 100000):
        raise HTTPException(status_code=422, detail="offset must be between 0 and 100000")

    # Import service
    try:
        from app.services.deps import PortService  # preferred
    except Exception:
        try:
            from app.services.dependencies import PortService  # fallback
        except Exception as _e:
            logger.error("PortService import failed: %s", _e)
            return []

    svc = PortService()
    try:
        data = await svc.get_port_calls_with_pagination(unlocode, start_date_obj, end_date_obj, limit, offset)
    except Exception as e:
        logger.error("get_port_calls_with_pagination failed for %s: %s", unlocode, e)
        return []

    if not data:
        return []

    result: List[_PortCallProcessed] = []

    for entry in data:
        # Derived metrics
        service_time = None
        if entry.atb and entry.atd:
            service_time = (entry.atd - entry.atb).total_seconds() / 3600.0

        turnaround_time = None
        if entry.ata and entry.atd:
            turnaround_time = (entry.atd - entry.ata).total_seconds() / 3600.0

        phase = None
        if entry.ata and not entry.atb:
            phase = "waiting"
        elif entry.atb and not entry.atd:
            phase = "berthing"
        elif entry.atd:
            phase = "turnaround"

        wait_hours = None
        if entry.ata and entry.atb:
            wait_hours = (entry.atb - entry.ata).total_seconds() / 3600.0

        result.append(
            _PortCallProcessed(
                call_id=entry.call_id,
                unlocode=entry.unlocode,
                phase=phase,
                wait_hours=wait_hours,
                service_time_hours=service_time,
                turnaround_hours=turnaround_time,
                updated_at=entry.last_updated_at,
            )
        )

    return result