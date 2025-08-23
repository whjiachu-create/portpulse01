from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
import logging

from app.models.port import PortOverview, PortCallExpanded, PortCallProcessed
from app.services.port_service import PortService
from app.utils.time_utils import parse_time_parameter
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ETag generation and matching utilities
def _strong_etag_from_text(text: str) -> str:
    """Generate a strong ETag from text content"""
    import hashlib
    etag_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    return f'"{etag_hash}"'

def _client_etags(request: Request) -> List[str]:
    """Extract ETags from If-None-Match header"""
    if_none_match = request.headers.get("if-none-match")
    if not if_none_match:
        return []
    
    # Split by comma and strip whitespace and quotes
    etags = [tag.strip().strip('"') for tag in if_none_match.split(",")]
    return etags

def _etag_matches(etag: str, client_etags: List[str]) -> bool:
    """Check if ETag matches any of client's ETags (weak comparison compatible)"""
    if not client_etags:
        return False
    
    # Strip quotes from our strong etag for comparison
    clean_etag = etag.strip('"')
    return clean_etag in client_etags

CSV_SOURCE_TAG = "ports:overview:strong-etag"

@router.api_route(
    "/{unlocode}/overview",
    methods=["GET", "HEAD"],
    summary="Port Overview",
    tags=["ports"],
)
async def port_overview(
    request: Request,
    unlocode: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None
) -> Union[Response, PlainTextResponse]:
    """
    Get port overview data in CSV format
    
    Supports both GET and HEAD methods with ETag-based caching.
    Returns 304 if ETag matches, 200 with headers only for HEAD, 
    and 200 with content for GET.
    """
    
    # Parse time parameters
    try:
        parsed_from_time = parse_time_parameter(from_time) if from_time else datetime.utcnow() - timedelta(days=1)
        parsed_to_time = parse_time_parameter(to_time) if to_time else datetime.utcnow() + timedelta(days=7)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Get data from service
    port_service = PortService()
    try:
        data = await port_service.get_port_overview(unlocode, parsed_from_time, parsed_to_time)
    except Exception as e:
        logger.error(f"Error fetching port overview for {unlocode}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    if not data:
        raise HTTPException(status_code=404, detail=f"Port with UNLOCODE {unlocode} not found")
    
    # Convert to CSV
    csv_lines = ["IMO,Name,Status,Last Port,Destination,Arrival,Departure,Reported,Lat,Lon,Speed,Course,Heading,Current Port"]
    
    for entry in data:
        # Format datetime fields
        arrival_str = entry.arrival.strftime("%Y-%m-%d %H:%M") if entry.arrival else ""
        departure_str = entry.departure.strftime("%Y-%m-%d %H:%M") if entry.departure else ""
        reported_str = entry.reported.strftime("%Y-%m-%d %H:%M") if entry.reported else ""
        
        line = f"{entry.imo},{entry.name},{entry.status},{entry.last_port}," \
               f"{entry.destination},{arrival_str},{departure_str},{reported_str}," \
               f"{entry.lat},{entry.lon},{entry.speed},{entry.course},{entry.heading},{entry.current_port}"
        csv_lines.append(line)
    
    csv_string = "\n".join(csv_lines)
    
    # Handle ETag and caching logic
    etag = _strong_etag_from_text(csv_string)
    client_tags = _client_etags(request)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Vary": "Accept-Encoding",
        "X-CSV-Source": CSV_SOURCE_TAG,
    }
    
    if _etag_matches(etag, client_tags):
        return Response(status_code=304, headers=headers)
    
    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)
    
    # Record timing
    logger.info(f"Port overview for {unlocode} generated successfully")
    
    return PlainTextResponse(
        content=csv_string,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )

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