from app.services.dependencies import require_api_key
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union, Tuple
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from hashlib import sha256
from typing import TYPE_CHECKING
import logging

# 修改导入语句，使用新创建的schemas而不是models
from app.schemas import (
    PortOverview as _PortOverview,
    PortCallExpanded as _PortCallExpanded,
    PortCallProcessed as _PortCallProcessed,
)

# 删除原有的异常处理导入

if TYPE_CHECKING:
    from app.schemas import PortOverview, PortCallExpanded, PortCallProcessed

router = APIRouter(dependencies=[Depends(require_api_key)], )

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