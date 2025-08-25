from fastapi import APIRouter, Response, Query
from fastapi.responses import Response as RawResponse
from typing import Optional, List, Dict
import io, csv

router = APIRouter()
CACHE_5M = "public, max-age=300"

@router.get("/sources", summary="List data sources")
def list_sources(response: Response):
    response.headers["Cache-Control"] = CACHE_5M
    return {"sources": ["ais", "port_authority", "carrier_feeds"]}

@router.get("/ports/{unlocode}/snapshot", summary="Port snapshot")
def port_snapshot(unlocode: str, response: Response):
    response.headers["Cache-Control"] = CACHE_5M
    return {
        "unlocode": unlocode.upper(),
        "snapshot": {"vessels": 0, "avg_wait_hours": 0.0}
    }

@router.get("/ports/{unlocode}/dwell", summary="Dwell stats")
def port_dwell(unlocode: str, days: int = Query(14, ge=1, le=180), response: Response = None):
    if response:
        response.headers["Cache-Control"] = CACHE_5M
    if unlocode.upper() == "NOPE":
        return []
    return [
        {"day": "2025-08-01", "avg_wait_hours": 10.5},
        {"day": "2025-08-02", "avg_wait_hours": 9.2},
    ]

@router.get("/ports/{unlocode}/trend", summary="Trend")
def port_trend(
    unlocode: str,
    days: int = Query(14, ge=1, le=365),
    fields: str = "vessels,avg_wait_hours",
    limit: int = Query(7, ge=0, le=1000),
    offset: int = Query(0, ge=0),
    fmt: Optional[str] = Query(None, alias="format", pattern="^(csv|json)$"),
    response: Response = None,
):
    cols = [c.strip() for c in fields.split(",") if c.strip()]
    pts: List[Dict[str, object]] = []
    for i in range(offset, offset + min(limit, 7)):
        pts.append({
            "day": f"2025-08-{(i % 28) + 1:02d}",
            "vessels": 12 + i,
            "avg_wait_hours": max(0.0, 15.0 - i),
        })

    if fmt == "csv":
        sio = io.StringIO()
        header = ["day"] + cols
        w = csv.writer(sio)
        w.writerow(header)
        for p in pts:
            w.writerow([p.get(c, "") for c in header])
        if response:
            response.headers["Cache-Control"] = CACHE_5M
        return RawResponse(content=sio.getvalue(), media_type="text/csv")

    return {
        "unlocode": unlocode.upper(),
        "points": pts
    }
