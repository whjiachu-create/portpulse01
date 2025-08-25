from fastapi import APIRouter, Query, Response, Request
from datetime import datetime, timedelta
from hashlib import sha256

router = APIRouter(tags=["hs"])

def _build_points(code: str, frm: str, to: str, months: int):
    # 伪数据（可重复、稳定）：按 (code,frm,to) 构造一个简单序列
    base = abs(hash((code, frm, to))) % 5000 + 10000
    today = datetime.utcnow().date().replace(day=1)
    pts = []
    for i in range(months, 0, -1):
        month = (today.replace(day=1) - timedelta(days=30*i)).replace(day=1)
        # 简单波动：避免随机
        val = base + (i * 37) % 1200
        pts.append({"month": month.isoformat(), "value": int(val), "src": "demo"})
    return pts

@router.get("/{code}/imports", summary="HS imports (demo)")
async def hs_imports(
    code: str,
    frm: str = Query(..., min_length=2, max_length=3, description="Origin ISO-2/3"),
    to:  str = Query(..., min_length=2, max_length=3, description="Destination ISO-2/3"),
    months: int = Query(6, ge=1, le=36),
    format: str = Query("json", pattern="^(json|csv)$"),
    request: Request = None,
):
    points = _build_points(code, frm, to, months)

    if format == "csv":
        rows = ["month,value,src"] + [f'{p["month"]},{p["value"]},{p["src"]}' for p in points]
        csv_text = "\n".join(rows) + "\n"
        etag = '"' + sha256(csv_text.encode("utf-8")).hexdigest() + '"'
        # 条件请求
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

    # JSON
    return {
        "code": code, "frm": frm, "to": to,
        "as_of": datetime.utcnow().isoformat() + "Z",
        "points": points,
    }
