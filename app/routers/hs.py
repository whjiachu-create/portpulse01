# app/routers/hs.py
from __future__ import annotations
from fastapi import APIRouter, Query, Response, Request, HTTPException
from datetime import datetime, timedelta
from hashlib import sha256
import os

router = APIRouter(tags=["hs"])

# --- Beta guard (minimal) ---

def _hs_beta_enabled() -> bool:
    return os.getenv("HS_IMPORTS_ENABLED", "").strip().lower() in ("1","true","yes","on")

def _ensure_hs_beta_open() -> None:
    if not _hs_beta_enabled():
        # 403 更贴近“功能关闭”，由全局 handler 包装成 {code,message,request_id,hint}
        raise HTTPException(
            status_code=403,
            detail="HS imports beta is closed"
        )

# --- Demo data builder ---

def _build_points(code: str, frm: str, to: str, months: int):
    base = abs(hash((code, frm, to))) % 5000 + 10000
    today = datetime.utcnow().date().replace(day=1)
    pts = []
    for i in range(months, 0, -1):
        month = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        val = base + (i * 37) % 1200
        pts.append({"month": month.isoformat(), "value": int(val), "src": "demo"})
    return pts

# --- Routes ---

@router.get("/{code}/imports", summary="HS imports (demo)")
async def hs_imports(
    code: str,
    frm: str = Query(..., min_length=2, max_length=3, description="Origin ISO-2/3"),
    to:  str = Query(..., min_length=2, max_length=3, description="Destination ISO-2/3"),
    months: int = Query(6, ge=1, le=36),
    format: str = Query("json", pattern="^(json|csv)$"),
    request: Request = None,
):
    _ensure_hs_beta_open()  # guard first

    points = _build_points(code, frm, to, months)

    if format == "csv":
        rows = ["month,value,src"] + [f'{p["month"]},{p["value"]},{p["src"]}' for p in points]
        csv_text = "\n".join(rows) + "\n"
        etag = '"' + sha256(csv_text.encode("utf-8")).hexdigest() + '"'
        inm = request.headers.get("if-none-match") if request else None
        if inm:
            cands = [s.strip() for s in inm.split(",")]
            if etag in cands or f"W/{etag}" in cands:
                return Response(status_code=304, headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=300, no-transform",
                    "Vary": "Accept-Encoding",
                })
        return Response(
            content=csv_text.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
            }
        )

    return {
        "code": code, "frm": frm, "to": to,
        "as_of": datetime.utcnow().isoformat() + "Z",
        "points": points,
    }

@router.head("/{code}/imports")
async def hs_imports_head(
    code: str,
    frm: str,
    to: str,
    months: int = 6,
    format: str = "json",
    request: Request = None,
):
    _ensure_hs_beta_open()  # guard first

    points = _build_points(code, frm, to, months)
    if format == "csv":
        rows = ["month,value,src"] + [f'{p["month"]},{p["value"]},{p["src"]}' for p in points]
        csv_text = "\n".join(rows) + "\n"
        etag = '"' + sha256(csv_text.encode("utf-8")).hexdigest() + '"'
        inm = request.headers.get("if-none-match") if request else None
        if inm:
            cands = [s.strip() for s in inm.split(",")]
            if etag in cands or f"W/{etag}" in cands:
                return Response(status_code=304, headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=300, no-transform",
                    "Vary": "Accept-Encoding",
                })
        return Response(status_code=200, headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=300, no-transform",
            "Vary": "Accept-Encoding",
        })
    return Response(status_code=200, headers={"Cache-Control": "public, max-age=60, no-transform"})