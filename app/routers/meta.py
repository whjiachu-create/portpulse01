from fastapi import APIRouter, Response
from datetime import datetime, timezone
from app.schemas import SourcesResponse, SourceItem

router = APIRouter(tags=["meta"])

@router.get("/sources", response_model=SourcesResponse, summary="List data sources")
async def list_sources(response: Response) -> SourcesResponse:
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    items = [
        SourceItem(name="AIS_A", description="Primary AIS aggregate", license="CC-BY", source_type="AIS"),
        SourceItem(name="PORT_BULLETIN", description="Port authority bulletins"),
    ]
    return SourcesResponse(sources=items, as_of=datetime.now(timezone.utc))
