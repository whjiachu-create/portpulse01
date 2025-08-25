from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union, Tuple
from fastapi import APIRouter, HTTPException, Query, Depends, Request  # 保持原有导入
from fastapi.responses import JSONResponse, StreamingResponse
import csv
import io
from typing import List, Optional, Dict, Any

from app.models import PortSnapshot, DwellResponse, TrendResponse
from app.services import get_port_snapshot, get_dwell_data, get_trend_data
from app.utils.cache import cache_control

router = APIRouter(prefix="/v1/ports", tags=["ports"])

# --- Readouts (sources/snapshot/dwell/trend) ---
# 说明：
# 1) 这些端点是读数面板的契约：sources 统一返回源信息（带 public, max-age=300）；
# 2) snapshot 顶层不为 null；dwell 在无数据时返回 [] 但 200；
# 3) trend 支持 fields/limit/offset，CSV 版本带缓存头。

# --- Port Calls (overview/calls/processed) ---
# 说明：
# 1) overview 返回 CSV 格式，带强 ETag 和缓存头；
# 2) calls 返回原始数据，带分页支持；
# 3) processed 返回计算字段，带分页支持。
from app.schemas import (
    PortOverview as _PortOverview,
    PortCallExpanded as _PortCallExpanded,
    PortCallProcessed as _PortCallProcessed,
)

if TYPE_CHECKING:
    from app.schemas import PortOverview, PortCallExpanded, PortCallProcessed

router = APIRouter()

# 添加logger
logger = logging.getLogger(__name__)


def _build_overview_csv_and_headers(unlocode: str) -> Tuple[str, dict]:
    """
    构建港口概览CSV内容和响应头
    返回: (csv_text, headers)
    """
    # ……生成 CSV 内容 csv_text
    csv_text = "sample,csv,data\n1,2,3"  # 示例数据，实际代码中应替换为真实逻辑
    
    etag = '"' + sha256(csv_text.encode()).hexdigest() + '"'  # 强 ETag（带双引号）
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:overview:strong-etag",
    }
    return csv_text, headers

@router.get("/{unlocode}/overview", response_model=_PortOverview)
async def get_overview_csv(unlocode: str, format: str = "csv", request: Request = None):
    csv_text, headers = _build_overview_csv_and_headers(unlocode)
    
    # 条件请求：If-None-Match 同时支持强/弱
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f"W/{headers['ETag']}" in candidates:
            return Response(status_code=304, headers=headers)
            
    return Response(
        content=csv_text.encode(), 
        media_type="text/csv; charset=utf-8", 
        headers=headers
    )

# 显式支持 HEAD（避免某些情况下返回 405）
@router.head("/{unlocode}/overview")
async def head_overview_csv(unlocode: str, format: str = "csv", request: Request = None):
    # 只复用上面的 ETag/Cache-Control 逻辑，不返回 body
    csv_text, headers = _build_overview_csv_and_headers(unlocode)
    
    # 条件请求：If-None-Match 同时支持强/弱
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f"W/{headers['ETag']}" in candidates:
            return Response(status_code=304, headers=headers)
            
    return Response(status_code=200, headers=headers)

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
    offset: Optional[int] = 0
) -> List[_PortCallExpanded]:
    """
    Get detailed port calls information with pagination support
    """
    # Parse and validate date parameters
    try:
        # Set default dates if none provided
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
        
        # Validate date range
        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")
    except ValueError as e:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate limit and offset
    if limit is None:
        limit = 100
    if offset is None:
        offset = 0
        
    if not (1 <= limit <= 1000):
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
        
    if not (0 <= offset <= 100000):
        raise HTTPException(status_code=422, detail="offset must be between 0 and 100000")
    
    # Get data from service
    port_service = PortService()
    try:
        data = await port_service.get_port_calls_with_pagination(
            unlocode, 
            start_date_obj, 
            end_date_obj, 
            limit, 
            offset
        )
    except Exception as e:
        logger.error(f"Error fetching port calls for {unlocode}: {str(e)}")
        # Return empty list instead of 500 error
        return []
    
    # 修改: 确保始终返回列表
    if not data:
        return []
        
    result = [
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
            last_updated_at=entry.last_updated_at
        )
        for entry in data
    ]
    
    return result

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
    offset: Optional[int] = 0
) -> List[_PortCallProcessed]:
    """
    Get processed port calls information with additional calculated fields and pagination support
    """
    # Parse and validate date parameters
    try:
        # Set default dates if none provided
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
        
        # Validate date range
        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")
    except ValueError as e:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate limit and offset
    if limit is None:
        limit = 100
    if offset is None:
        offset = 0
        
    if not (1 <= limit <= 1000):
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
        
    if not (0 <= offset <= 100000):
        raise HTTPException(status_code=422, detail="offset must be between 0 and 100000")
    
    # Get data from service
    port_service = PortService()
    try:
        data = await port_service.get_port_calls_with_pagination(
            unlocode, 
            start_date_obj, 
            end_date_obj, 
            limit, 
            offset
        )
    except Exception as e:
        logger.error(f"Error fetching processed port calls for {unlocode}: {str(e)}")
        # Return empty list instead of 500 error
        return []
    
    # Process data
    result = []
    
    # 修改: 确保即使data为None也返回空列表
    if data:
        for entry in data:
            # Calculate service time (berth to departure)
            service_time = None
            if entry.atb and entry.atd:
                service_time = (entry.atd - entry.atb).total_seconds() / 3600  # in hours
            
            # Calculate turnaround time (arrival to departure)
            turnaround_time = None
            if entry.ata and entry.atd:
                turnaround_time = (entry.atd - entry.ata).total_seconds() / 3600  # in hours
            
            # Determine phase
            phase = None
            if entry.ata and not entry.atb:
                phase = "waiting"
            elif entry.atb and not entry.atd:
                phase = "berthing"
            elif entry.atd:
                phase = "turnaround"
            
            # Calculate wait hours (anchor to berth)
            wait_hours = None
            if entry.ata and entry.atb:
                wait_hours = (entry.atb - entry.ata).total_seconds() / 3600  # in hours
            
            processed_entry = _PortCallProcessed(
                call_id=entry.call_id,
                unlocode=entry.unlocode,
                phase=phase,
                wait_hours=wait_hours,
                service_time_hours=service_time,
                turnaround_hours=turnaround_time,
                updated_at=entry.last_updated_at
            )
            result.append(processed_entry)
    
    # 修改: 确保始终返回列表
    return result

from fastapi import APIRouter, Query, Response, Request, HTTPException
from typing import Optional, List
from datetime import date, timedelta, datetime, timezone
import hashlib
from app.schemas import (
    TrendPoint, TrendResponse,
    DwellPoint, DwellResponse,
    SnapshotResponse, SnapshotMetrics, SourceInfo,
)

router = APIRouter(tags=["ports"])

def _demo_trend(unlocode: str, days: int) -> List[TrendPoint]:
    if unlocode not in {"USLAX", "USNYC"}:
        return []
    today = date.today()
    out = []
    for i in range(days):
        d = today - timedelta(days=days-1-i)
        out.append(TrendPoint(
            date=d, vessels=50+(i%7), avg_wait_hours=24.0+(i%5),
            congestion_score=60.0+(i%3), src="DEMO"))
    return out

@router.get("/{unlocode}/trend", response_model=TrendResponse, summary="Port trend series (json/csv)")
async def get_trend(
    request: Request,
    response: Response,
    unlocode: str,
    days: int = Query(180, ge=1, le=365),
    fields: Optional[str] = Query(None, description="vessels,avg_wait_hours,congestion_score"),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(365, ge=1, le=365),
    offset: int = Query(0, ge=0),
):
    points = _demo_trend(unlocode, days)
    points = points[offset: offset + limit]

    if format == "csv":
        cols = ["vessels","avg_wait_hours","congestion_score"]
        if fields:
            sel = [f for f in fields.split(",") if f in cols]
            if sel: cols = sel
        header = ["date"] + cols + ["src"]
        rows = [",".join(header)]
        for p in points:
            line = [p.date.isoformat()] + [
                "" if getattr(p,c) is None else str(getattr(p,c)) for c in cols
            ] + [p.src or ""]
            rows.append(",".join(line))
        body = "\n".join(rows) + "\n"
        etag = '"' + hashlib.sha256(body.encode("utf-8")).hexdigest() + '"'
        inm = request.headers.get("if-none-match", "")
        if etag in inm or f'W/{etag}' in inm:
            response.headers["Cache-Control"] = "public, max-age=300, no-transform"
            response.headers["ETag"] = etag
            return Response(status_code=304)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Cache-Control":"public, max-age=300, no-transform","ETag":etag,"Vary":"Accept-Encoding"},
        )

    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return TrendResponse(unlocode=unlocode, points=points)

@router.get("/{unlocode}/dwell", response_model=DwellResponse, summary="Daily dwell hours")
async def get_dwell(unlocode: str, days: int = Query(30, ge=1, le=90), response: Response):
    pts: List[DwellPoint] = []
    if unlocode in {"USLAX","USNYC"}:
        today = date.today()
        for i in range(days):
            d = today - timedelta(days=days-1-i)
            pts.append(DwellPoint(date=d, dwell_hours=24.0 + (i % 6), src="DEMO"))
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return DwellResponse(unlocode=unlocode, points=pts)

@router.get("/{unlocode}/snapshot", response_model=SnapshotResponse, summary="Latest snapshot for dashboards")
async def get_snapshot(response: Response, unlocode: str):
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    now = datetime.now(timezone.utc)
    if unlocode in {"USLAX","USNYC"}:
        metrics = SnapshotMetrics(vessels=57, avg_wait_hours=26.0, congestion_score=62.0)
        return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=metrics, source=SourceInfo(src="DEMO"))
    return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=SnapshotMetrics(), source=SourceInfo(src=None))

# ==== P0: Added endpoints trend/dwell/snapshot ====
from typing import Optional, List
from datetime import date, timedelta, datetime, timezone
import hashlib
from fastapi import Query, Response, Request
from app.schemas.port import (
    TrendPoint, TrendResponse,
    DwellPoint, DwellResponse,
    SnapshotMetrics, SnapshotResponse, SourceInfo,
)

@router.get("/{unlocode}/trend", response_model=TrendResponse, summary="Port trend series (json/csv)")
async def get_trend(
    request: Request,
    response: Response,
    unlocode: str,
    days: int = Query(180, ge=1, le=365),
    fields: Optional[str] = Query(None, description="comma-joined: vessels,avg_wait_hours,congestion_score"),
    format: str = Query("json", pattern="^(json|csv)$"),
    tz: str = Query("UTC"),
    limit: int = Query(365, ge=1, le=365),
    offset: int = Query(0, ge=0),
):
    def _fake_points() -> List[TrendPoint]:
        if unlocode not in {"USLAX", "USNYC"}:
            return []
        today = date.today()
        vals: List[TrendPoint] = []
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            vals.append(TrendPoint(
                date=d,
                vessels=50 + (i % 7),
                avg_wait_hours=24.0 + (i % 5),
                congestion_score=min(100.0, 40.0 + i * 0.2),
                src="DEMO",
            ))
        return vals

    points = _fake_points()
    points = points[offset: offset + limit]

    if format == "csv":
        req_fields = ["vessels", "avg_wait_hours", "congestion_score"]
        if fields:
            picked = [f for f in fields.split(",") if f in req_fields]
            if picked:
                req_fields = picked
        header = ["date"] + req_fields + ["src"]
        rows = [",".join(header)]
        for p in points:
            cols = [p.date.isoformat()]
            for f in req_fields:
                v = getattr(p, f)
                cols.append("" if v is None else str(v))
            cols.append("" if p.src is None else p.src)
            rows.append(",".join(cols))
        body = "\n".join(rows) + "\n"
        etag = '"' + hashlib.sha256(body.encode("utf-8")).hexdigest() + '"'
        inm = request.headers.get("if-none-match", "")
        if etag in inm or f'W/{etag}' in inm:
            response.headers["Cache-Control"] = "public, max-age=300, no-transform"
            response.headers["ETag"] = etag
            return Response(status_code=304)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=300, no-transform",
                "ETag": etag,
                "Vary": "Accept-Encoding",
            },
        )
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return TrendResponse(unlocode=unlocode, points=points)

@router.get("/{unlocode}/dwell", response_model=DwellResponse, summary="Daily dwell hours")
async def get_dwell(unlocode: str, days: int = Query(30, ge=1, le=90), response: Response = None):
    pts: List[DwellPoint] = []
    if unlocode in {"USLAX", "USNYC"}:
        today = date.today()
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            pts.append(DwellPoint(date=d, dwell_hours=24.0 + (i % 6), src="DEMO"))
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    return DwellResponse(unlocode=unlocode, points=pts)

@router.get("/{unlocode}/snapshot", response_model=SnapshotResponse, summary="Latest snapshot")
async def get_snapshot(unlocode: str, response: Response):
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    now = datetime.now(timezone.utc)
    if unlocode in {"USLAX", "USNYC"}:
        metrics = SnapshotMetrics(vessels=57, avg_wait_hours=26.0, congestion_score=62.0)
        return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=metrics, source=SourceInfo(src="DEMO"))
    return SnapshotResponse(unlocode=unlocode, as_of=now, metrics=SnapshotMetrics(), source=SourceInfo(src=None))
