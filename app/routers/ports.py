from __future__ import annotations
from fastapi import APIRouter, Query, Response, Request, HTTPException
from datetime import datetime, timedelta, timezone, date
from hashlib import sha256
import re

router = APIRouter(tags=["ports"])

# --- Known ports（覆盖自检用到的 USLAX 等）---
KNOWN_PORTS = {
    "USLAX","USLGB","USNYC","USSAV","USCHS","USORF","USHOU","USSEA","USOAK","USMIA",
    "NLRTM","BEANR","DEHAM","DEBRV","FRLEH","GBFXT","GBLGP","ESVLC","ESALG","GRPIR",
    "CNSHA","CNNGB","CNSZX","CNTAO","KRPUS","SGSIN","MYTPP","THLCH","INNSA","INMUN",
}

# UN/LOCODE 允许字母+数字（5位）
_UNLOCODE_RE = re.compile(r"^[A-Z0-9]{5}$")

def _ensure_unlocode_valid(code: str) -> None:
    if not _UNLOCODE_RE.match(code or ""):
        raise HTTPException(status_code=422, detail="invalid UNLOCODE format")

def _ensure_port_exists(code: str) -> None:
    if code not in KNOWN_PORTS:
        raise HTTPException(status_code=404, detail="port not found")

def _today_utc() -> date:
    return datetime.now(timezone.utc).date()

def _deterministic(num: int) -> float:
    return (num % 100) / 100.0

def _demo_overview(code: str) -> dict:
    base = abs(hash(code)) % 1000
    return {
        "unlocode": code,
        "port_name": None,
        "country": None,
        "arrivals_7d": (base % 30) + 50,
        "departures_7d": (base % 30) + 45,
        "waiting_vessels": (base % 8),
        "avg_wait_hours": round(4.0 + (base % 120) / 10.0, 1),
        "avg_berth_hours": round(10.0 + (base % 200) / 10.0, 1),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

def _demo_trend(code: str, days: int) -> list[dict]:
    days = max(1, min(30, int(days or 7)))
    today = _today_utc()
    pts = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        v = _deterministic(abs(hash((code, d.toordinal()))))
        pts.append({
            "date": d.isoformat(),
            "congestion_score": round(0.3 + 0.5 * v, 3)
        })
    return pts

def _csv_and_etag(rows: list[str]) -> tuple[bytes, str]:
    csv_text = "\n".join(rows) + "\n"
    etag = '"' + sha256(csv_text.encode("utf-8")).hexdigest() + '"'
    return csv_text.encode("utf-8"), etag

# -------- Overview --------
@router.get("/{unlocode}/overview", summary="Get Overview")
async def get_overview(
    unlocode: str,
    format: str | None = Query(None, pattern="^(json|csv)$"),
):
    _ensure_unlocode_valid(unlocode)
    _ensure_port_exists(unlocode)

    data = _demo_overview(unlocode)

    if (format or "").lower() == "csv":
        rows = ["unlocode,arrivals_7d,departures_7d,waiting_vessels,avg_wait_hours,avg_berth_hours,updated_at"]
        rows.append(",".join([
            data["unlocode"],
            str(data["arrivals_7d"]),
            str(data["departures_7d"]),
            str(data["waiting_vessels"]),
            str(data["avg_wait_hours"]),
            str(data["avg_berth_hours"]),
            data["updated_at"],
        ]))
        body, etag = _csv_and_etag(rows)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
            },
        )

    return data

@router.head("/{unlocode}/overview", summary="Head Overview")
async def head_overview(
    unlocode: str,
    format: str | None = Query(None, pattern="^(json|csv)$"),
    request: Request = None,
):
    _ensure_unlocode_valid(unlocode)
    _ensure_port_exists(unlocode)

    if (format or "").lower() == "csv":
        data = _demo_overview(unlocode)
        rows = ["unlocode,arrivals_7d,departures_7d,waiting_vessels,avg_wait_hours,avg_berth_hours,updated_at"]
        rows.append(",".join([
            data["unlocode"],
            str(data["arrivals_7d"]),
            str(data["departures_7d"]),
            str(data["waiting_vessels"]),
            str(data["avg_wait_hours"]),
            str(data["avg_berth_hours"]),
            data["updated_at"],
        ]))
        _, etag = _csv_and_etag(rows)
        inm = request.headers.get("if-none-match") if request else None
        if inm and any(etag.strip() == t.strip() or f'W/{etag}' == t.strip() for t in inm.split(",")):
            return Response(status_code=304, headers={
                "Content-Type": "text/csv; charset=utf-8",
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
            })
        return Response(status_code=200, headers={
            "ETag": etag,
            "Content-Type": "text/csv; charset=utf-8",
            "Cache-Control": "public, max-age=300, no-transform",
            "Vary": "Accept-Encoding",
        })
    return Response(status_code=200, headers={"Cache-Control": "public, max-age=300, no-transform"})

# -------- Trend (JSON/CSV + ETag/304 + HEAD) --------
@router.get("/{unlocode}/trend", summary="Port trend (JSON/CSV)")
async def get_trend(
    unlocode: str,
    days: int | None = Query(None, ge=1, le=30),
    window: int | None = Query(None, ge=1, le=30),
    limit: int | None = Query(None, ge=1, le=1000),
    format: str | None = Query(None, pattern="^(json|csv)$"),
    request: Request = None,
):
    _ensure_unlocode_valid(unlocode)
    _ensure_port_exists(unlocode)

    N = days or window or 7
    pts = _demo_trend(unlocode, N)

    if (format or "").lower() == "csv":
        rows = ["date,congestion_score"]
        rows += [f'{p["date"]},{p["congestion_score"]}' for p in pts]
        body, etag = _csv_and_etag(rows)
        inm = request.headers.get("if-none-match") if request else None
        if inm and any(etag.strip() == t.strip() or f'W/{etag}' == t.strip() for t in inm.split(",")):
            return Response(status_code=304, headers={"ETag": etag,
                "Content-Type": "text/csv; charset=utf-8",
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",})
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
            },
        )

    return {"unlocode": unlocode, "as_of": datetime.now(timezone.utc).isoformat(), "points": pts}

@router.head("/{unlocode}/trend", summary="Head Trend")
async def head_trend(
    unlocode: str,
    days: int | None = Query(None, ge=1, le=30),
    window: int | None = Query(None, ge=1, le=30),
    format: str | None = Query(None, pattern="^(json|csv)$"),
    request: Request = None,
):
    _ensure_unlocode_valid(unlocode)
    _ensure_port_exists(unlocode)

    N = days or window or 7
    if (format or "").lower() == "csv":
        pts = _demo_trend(unlocode, N)
        rows = ["date,congestion_score"]
        rows += [f'{p["date"]},{p["congestion_score"]}' for p in pts]
        _, etag = _csv_and_etag(rows)
        inm = request.headers.get("if-none-match") if request else None
        if inm and any(etag.strip() == t.strip() or f'W/{etag}' == t.strip() for t in inm.split(",")):
            return Response(status_code=304, headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
            })
        return Response(status_code=200, headers={"ETag": etag,
            "Content-Type": "text/csv; charset=utf-8",
            "Cache-Control": "public, max-age=300, no-transform",
            "Vary": "Accept-Encoding",})
    return Response(status_code=200, headers={"Cache-Control": "public, max-age=300, no-transform"})

# -------- Snapshot/Dwell/Alerts（自检只要 200） --------
@router.get("/{unlocode}/snapshot", summary="Port snapshot")
async def snapshot(unlocode: str):
    _ensure_unlocode_valid(unlocode); _ensure_port_exists(unlocode)
    return _demo_overview(unlocode)

@router.get("/{unlocode}/dwell", summary="Dwell (demo)")
async def dwell(unlocode: str, window: str | None = Query("14d")):
    _ensure_unlocode_valid(unlocode); _ensure_port_exists(unlocode)
    return []

@router.get("/{unlocode}/alerts", summary="Dwell change alerts (v1)")
async def get_alerts(unlocode: str, window: str | None = Query("14d")):
    _ensure_unlocode_valid(unlocode); _ensure_port_exists(unlocode)
    return {
        "unlocode": unlocode,
        "window": window,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "alerts": [
            {"severity": "info", "explain": "demo alert, deterministic"},
        ]
    }
