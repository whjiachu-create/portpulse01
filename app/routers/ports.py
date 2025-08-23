from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Request, Response
from hashlib import sha256
from app.models import PortOverview, PortCallExpanded, PortCallProcessed

router = APIRouter()

@router.get("/{unlocode}/overview")
async def get_overview_csv(unlocode: str, format: str = "csv", request: Request = None):
    # ……生成 CSV 内容 csv_bytes
    csv_bytes = b"sample,csv,data\n1,2,3"  # 示例数据，实际代码中应替换为真实逻辑
    
    etag = '"' + sha256(csv_bytes).hexdigest() + '"'  # 强 ETag（带双引号）
    # 条件请求：If-None-Match 同时支持强/弱
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if etag in candidates or f"W/{etag}" in candidates:
            return Response(status_code=304)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:overview:strong-etag",
    }
    return Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers=headers)

# 显式支持 HEAD（避免某些情况下返回 405）
@router.head("/{unlocode}/overview")
async def head_overview_csv(unlocode: str, format: str = "csv", request: Request = None):
    # 只复用上面的 ETag/Cache-Control 逻辑，不返回 body
    # ……生成 CSV 内容 csv_bytes
    csv_bytes = b"sample,csv,data\n1,2,3"  # 示例数据，实际代码中应替换为真实逻辑
    
    etag = '"' + sha256(csv_bytes).hexdigest() + '"'  # 强 ETag（带双引号）
    # 条件请求：If-None-Match 同时支持强/弱
    inm = request.headers.get("if-none-match") if request else None
    if inm:
        candidates = [s.strip() for s in inm.split(",")]
        if etag in candidates or f"W/{etag}" in candidates:
            return Response(status_code=304)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "x-csv-source": "ports:overview:strong-etag",
    }
    return Response(status_code=200, headers=headers)

@router.get(
    "/{unlocode}/calls",
    response_model=List[PortCallExpanded],
    summary="Port Calls",
    tags=["ports"],
)
async def port_calls(
    unlocode: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None
) -> List[PortCallExpanded]:
    """
    Get detailed port calls information
    """
    # Parse time parameters
    try:
        parsed_from_time = parse_time_parameter(from_time) if from_time else datetime.utcnow() - timedelta(days=7)
        parsed_to_time = parse_time_parameter(to_time) if to_time else datetime.utcnow() + timedelta(days=1)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate sort parameter
    valid_sort_options = ['arrival', 'departure', 'reported', 'imo']
    if sort and sort not in valid_sort_options:
        raise HTTPException(status_code=400, detail=f"Invalid sort option. Valid options: {valid_sort_options}")
    
    # Get data from service
    port_service = PortService()
    try:
        data = await port_service.get_port_calls(unlocode, parsed_from_time, parsed_to_time)
    except Exception as e:
        logger.error(f"Error fetching port calls for {unlocode}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"Port with UNLOCODE {unlocode} not found")
    
    # Convert to response model
    result = [
        PortCallExpanded(
            imo=entry.imo,
            name=entry.name,
            status=entry.status,
            last_port=entry.last_port,
            destination=entry.destination,
            arrival=entry.arrival,
            departure=entry.departure,
            reported=entry.reported,
            lat=entry.lat,
            lon=entry.lon,
            speed=entry.speed,
            course=entry.course,
            heading=entry.heading,
            current_port=entry.current_port
        )
        for entry in data
    ]
    
    # Apply sorting
    if sort:
        reverse = sort in ['arrival', 'departure', 'reported']
        result.sort(key=lambda x: getattr(x, sort) or (datetime.min if reverse else datetime.max), reverse=reverse)
    
    # Apply limit
    if limit and limit > 0:
        result = result[:limit]
    
    return result

@router.get(
    "/{unlocode}/calls/processed",
    response_model=List[PortCallProcessed],
    summary="Processed Port Calls",
    tags=["ports"],
)
async def processed_port_calls(
    unlocode: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None
) -> List[PortCallProcessed]:
    """
    Get processed port calls information with additional calculated fields
    """
    # Parse time parameters
    try:
        parsed_from_time = parse_time_parameter(from_time) if from_time else datetime.utcnow() - timedelta(days=7)
        parsed_to_time = parse_time_parameter(to_time) if to_time else datetime.utcnow() + timedelta(days=1)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate sort parameter
    valid_sort_options = ['arrival', 'departure', 'reported', 'imo', 'time_in_port']
    if sort and sort not in valid_sort_options:
        raise HTTPException(status_code=400, detail=f"Invalid sort option. Valid options: {valid_sort_options}")
    
    # Get data from service
    port_service = PortService()
    try:
        data = await port_service.get_port_calls(unlocode, parsed_from_time, parsed_to_time)
    except Exception as e:
        logger.error(f"Error fetching processed port calls for {unlocode}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"Port with UNLOCODE {unlocode} not found")
    
    # Process data
    result = []
    for i, entry in enumerate(data):
        # Calculate time in port
        time_in_port = None
        if entry.arrival and entry.departure:
            time_in_port = (entry.departure - entry.arrival).total_seconds() / 3600  # in hours
        
        # Determine next port
        next_port = None
        if i < len(data) - 1:
            next_port = data[i + 1].destination
        
        processed_entry = PortCallProcessed(
            imo=entry.imo,
            name=entry.name,
            status=entry.status,
            last_port=entry.last_port,
            destination=entry.destination,
            arrival=entry.arrival,
            departure=entry.departure,
            reported=entry.reported,
            lat=entry.lat,
            lon=entry.lon,
            speed=entry.speed,
            course=entry.course,
            heading=entry.heading,
            current_port=entry.current_port,
            time_in_port=time_in_port,
            next_port=next_port
        )
        result.append(processed_entry)
    
    # Apply sorting
    if sort:
        reverse = sort in ['arrival', 'departure', 'reported']
        if sort == 'time_in_port':
            result.sort(key=lambda x: x.time_in_port or (0 if reverse else float('inf')), reverse=reverse)
        else:
            result.sort(key=lambda x: getattr(x, sort) or (datetime.min if reverse else datetime.max), reverse=reverse)
    
    # Apply limit
    if limit and limit > 0:
        result = result[:limit]
    
    return result