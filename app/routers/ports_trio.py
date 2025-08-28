from app.services.dependencies import require_api_key
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, Response, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
import hashlib, csv, io

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["ports"])

# --- 简易稳定序列（可复现，便于 P1 验收；后续替换为真实数据） ---
def _series_base(unlocode:str, days:int, field:str)->List[dict]:
    base = (abs(hash(unlocode)) % 7) + 24
    today = date.today()
    pts=[]
    for i in range(days):
        d = today - timedelta(days=days - i)
        v = base + ((i*5) % 9)
        if unlocode in {"USLAX","USNYC","USNYN"} and i>days//2:
            v += 3.0
        pts.append({"date": d.isoformat(), field: round(float(v),2), "src": "demo"})
    return pts

def _trend_points(unlocode:str, days:int)->List[dict]:
    # 最小字段：vessels/avg_wait_hours/congestion_score
    pts=[]
    a=_series_base(unlocode, days, "avg_wait_hours")
    for i, p in enumerate(a):
        pts.append({
            "date": p["date"],
            "vessels": 80 + (i*3)%40,
            "avg_wait_hours": p["avg_wait_hours"],
            "congestion_score": min(100, int(50 + p["avg_wait_hours"] - 24)),
            "src": "demo"
        })
    return pts

def _csv_bytes(rows:List[dict], fields:List[str])->bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows: w.writerow({k:r.get(k,"") for k in fields})
    return buf.getvalue().encode("utf-8")

def _etag(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def _limit_offset(rows:List[dict], limit:int, offset:int)->List[dict]:
    if offset<0: offset=0
    if limit<=0: return rows[offset:]
    return rows[offset: offset+limit]

# --------- /v1/ports/{unlocode}/trend ----------
@router.get("/{unlocode}/trend", summary="Daily trend (JSON/CSV)")
async def trend(unlocode:str,
                request: Request,
                response: Response,
                days:int=Query(30, ge=1, le=365),
                fields:Optional[str]=Query(None, description="csv/json fields, comma-separated"),
                limit:int=Query(0, ge=0),
                offset:int=Query(0, ge=0),
                format:str=Query("json", pattern="^(json|csv)$")):
    response.headers["Cache-Control"]="public, max-age=300, no-transform"
    rows = _trend_points_from_file(unlocode, days) or _trend_points(unlocode, days)
    rows=_limit_offset(rows, limit, offset)

    
    if format=="csv":
        all_fields=["date","vessels","avg_wait_hours","congestion_score","src"]
        use_fields = [f for f in (fields.split(",") if fields else all_fields) if f in all_fields]
        if not use_fields: use_fields = all_fields
        body=_csv_bytes(rows, use_fields)
        et=_etag(body)
        etag_value=f"\"{et}\""
        cache_hdrs={"ETag": etag_value, "Cache-Control": "public, max-age=300, no-transform"}
        inm = request.headers.get("if-none-match")
        if inm and inm.strip('"')==et:
            from fastapi import Response
            return Response(status_code=304, headers=cache_hdrs)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            status_code=200,
            content=body.decode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers=cache_hdrs,
        )

    # json
    if fields:
        keep=set(fields.split(","))
        rows=[{k:v for k,v in r.items() if k in keep or k=="date"} for r in rows]
    return {"unlocode": unlocode, "points": rows}


import json, pathlib
def _try_read_dwell_file(unlocode:str, days:int):
    fp = pathlib.Path(f"data/derived/dwell/{unlocode.upper()}.json")
    if not fp.exists(): return None
    try:
        pts = (json.loads(fp.read_text(encoding="utf-8")) or {}).get("points",[])
        pts = [p for p in pts if p.get("date")]  # safety
        # 截取最近 days
        pts = pts[-days:]
        return pts
    except Exception:
        return None

# --------- /v1/ports/{unlocode}/dwell ----------
@router.get("/{unlocode}/dwell", summary="Daily dwell hours")
async def dwell(unlocode:str, response:Response, days:int=Query(30, ge=1, le=365)):
    response.headers["Cache-Control"]="public, max-age=300, no-transform"
    try:
        pts=_series_base(unlocode, days, "dwell_hours")
        return {"unlocode": unlocode, "points": pts}
    except Exception:
        # 永不 500：空返回
        return {"unlocode": unlocode, "points": []}

# --------- /v1/ports/{unlocode}/snapshot ----------
@router.get("/{unlocode}/snapshot", summary="Latest snapshot (top-level not null)")
async def snapshot(unlocode:str, response:Response):
    response.headers["Cache-Control"]="public, max-age=300, no-transform"
    # 最近一天的快照（从 trend 衍生）
    pts=_trend_points(unlocode, 1)
    if not pts:
        return {"unlocode": unlocode, "as_of": None, "metrics": {}, "source": {"src": None}}
    p=pts[-1]
    return {
        "unlocode": unlocode,
        "as_of": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat()+"Z", "as_of_date": p["date"],
        "metrics": {
            "vessels": p["vessels"],
            "avg_wait_hours": p["avg_wait_hours"],
            "congestion_score": p["congestion_score"]
        },
        "source": {"src": p["src"]}
    }

from pathlib import Path as _PP
import json as _JSON
def _trend_points_from_file(_u:str, _days:int):
    _p=_PP(f"data/derived/trend/{_u}.json")
    if _p.exists():
        try:
            _pts=_JSON.loads(_p.read_text(encoding="utf-8")).get("points",[])
            if _days>0: _pts=_pts[-_days:]
            return _pts
        except Exception:
            return None
    return None
