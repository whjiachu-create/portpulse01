from app.services.dependencies import require_api_key
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union, Tuple
from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query
from hashlib import sha256
from typing import TYPE_CHECKING
import logging
import io, csv

# 修改导入语句，使用新创建的schemas而不是models
from app.schemas import (
    PortOverview as _PortOverview,
    PortCallExpanded as _PortCallExpanded,
    PortCallProcessed as _PortCallProcessed,
)

from app.services.overrides import (
    load_trend_override,
    latest_from_points,
    snapshot_from_override,
    enforce_window,
)

# 删除原有的异常处理导入

if TYPE_CHECKING:
    from app.schemas import PortOverview, PortCallExpanded, PortCallProcessed

router = APIRouter(dependencies=[Depends(require_api_key)], )

# 添加logger
logger = logging.getLogger(__name__)

def _build_trend_csv_and_headers(unlocode: str, points: List[Dict]) -> Tuple[str, dict]:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["date","vessels","avg_wait_hours","congestion_score","src","as_of"])
    for p in points:
        writer.writerow([
            p.get("date"),
            p.get("vessels"),
            p.get("avg_wait_hours"),
            p.get("congestion_score"),
            p.get("src"),
            p.get("as_of"),
        ])
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
    构建港口概览CSV内容和响应头
    返回: (csv_text, headers)
    """
    # 尝试从覆盖层构造 snapshot；否则给出安全兜底
    snap = snapshot_from_override(unlocode)
    if not isinstance(snap, dict):
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
    writer.writerow([
        snap.get("unlocode"),
        snap.get("as_of"),
        snap.get("as_of_date"),
        (snap.get("metrics") or {}).get("vessels"),
        (snap.get("metrics") or {}).get("avg_wait_hours"),
        (snap.get("metrics") or {}).get("congestion_score"),
        (snap.get("source") or {}).get("src"),
    ])

    csv_text = buf.getvalue()
    etag = '"' + sha256(csv_text.encode()).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:overview:strong-etag",
    }
    return csv_text, headers

@router.get("/{unlocode}/overview")
async def get_overview_csv(
    unlocode: str,
    format: str = Query("csv", pattern="^(json|csv)$"),
    request: Request = None
):
    # 如果请求 json，则直接返回快照 JSON（与 /snapshot 保持一致的结构）
    if format.lower() == "json":
        snap = snapshot_from_override(unlocode)
        if not isinstance(snap, dict):
            snap = {
                "unlocode": unlocode.upper(),
                "as_of": None,
                "as_of_date": None,
                "metrics": {"vessels": None, "avg_wait_hours": None, "congestion_score": None},
                "source": {"src": "demo"},
            }
        return snap

    # 否则走 CSV（强 ETag + 304）
    csv_text, headers = _build_overview_csv_and_headers(unlocode)

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
async def head_overview_csv(
    unlocode: str,
    format: str = Query("csv", pattern="^(json|csv)$"),
    request: Request = None
):
    # 只复用上面的 ETag/Cache-Control 逻辑，不返回 body
    csv_text, headers = _build_overview_csv_and_headers(unlocode)

    # 条件请求：If-None-Match 同时支持强/弱
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f"W/{headers['ETag']}" in candidates:
            return Response(status_code=304, headers=headers)

    return Response(status_code=200, headers=headers)

@router.get("/{unlocode}/trend", summary="Port trend (JSON/CSV)")
async def port_trend(unlocode: str, window: int = Query(7, ge=1, le=30), format: str = Query("json", pattern="^(json|csv)$"), request: Request = None):
    # 优先读取覆盖文件
    ov = load_trend_override(unlocode, window)
    points = (ov or {}).get("points", [])

    # 窗口保护（即便 override 未按 window 过滤，也在此切片一次）
    if window and len(points) > window:
        points = points[-window:]

    if format.lower() == "json":
        # 返回统一结构 {unlocode, points}，并做二次窗口兜底
        payload = {"unlocode": unlocode.upper(), "points": points}
        payload = enforce_window(payload, window)
        return payload
    elif format.lower() == "csv":
        # 二次窗口兜底后再生成 CSV/ETag
        payload = enforce_window({"unlocode": unlocode.upper(), "points": points}, window)
        csv_text, headers = _build_trend_csv_and_headers(unlocode, payload["points"])
        inm = request.headers.get("if-none-match") if request else None
        if inm:
            candidates = [s.strip() for s in inm.split(",")]
            if headers["ETag"] in candidates or f"W/{headers['ETag']}" in candidates:
                return Response(status_code=304, headers=headers)
        return Response(content=csv_text.encode(), media_type="text/csv; charset=utf-8", headers=headers)
    else:
        raise HTTPException(status_code=422, detail="format must be 'json' or 'csv'")


@router.head("/{unlocode}/trend")
async def head_port_trend(unlocode: str, window: int = Query(7, ge=1, le=30), format: str = Query("csv", pattern="^(json|csv)$"), request: Request = None):
    # 仅用于 ETag/304 触发，默认走 csv

    ov = load_trend_override(unlocode, window)
    payload = enforce_window(
        {"unlocode": unlocode.upper(), "points": (ov or {}).get("points", [])},
        window
    )
    csv_text, headers = _build_trend_csv_and_headers(unlocode, payload["points"])
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if headers["ETag"] in candidates or f"W/{headers['ETag']}" in candidates:
            return Response(status_code=304, headers=headers)
    return Response(status_code=200, headers=headers)


@router.get("/{unlocode}/snapshot", response_model=_PortOverview, summary="Port snapshot")
async def port_snapshot(unlocode: str) -> Dict[str, Any]:
    # 优先使用覆盖快照（若存在 data/overrides/<PORT>/trend.json 则从最新点构造）
    ov_snap = snapshot_from_override(unlocode)
    if ov_snap:
        return ov_snap

    # 覆盖不存在时的保底（与线上示例一致，避免 500）
    return {
        "unlocode": unlocode.upper(),
        "as_of": None,
        "as_of_date": None,
        "metrics": {"vessels": None, "avg_wait_hours": None, "congestion_score": None},
        "source": {"src": "demo"},
    }

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

    try:
        from app.services.deps import PortService  # preferred
    except Exception:
        try:
            from app.services.dependencies import PortService  # fallback
        except Exception as _e:
            logger.error(f"PortService import failed: {_e}")
            return []

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

    try:
        return result
    except Exception:
        return []

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

    try:
        from app.services.deps import PortService  # preferred
    except Exception:
        try:
            from app.services.dependencies import PortService  # fallback
        except Exception as _e:
            logger.error(f"PortService import failed: {_e}")
            return []

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

    try:
        return result
    except Exception:
        return []