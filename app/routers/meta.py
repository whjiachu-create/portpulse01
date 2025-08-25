from fastapi import APIRouter, Response
from datetime import datetime, timezone
from app.schemas import SourcesResponse, SourceItem

router = APIRouter(tags=["meta"])

@router.get("/sources", response_model=SourcesResponse, summary="List data sources")
async def list_sources(response: Response) -> SourcesResponse:
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    items = [
        SourceItem(id="ais_a", name="AIS Provider A", license="CC-BY"),
        SourceItem(id="port_bulletin", name="Port Bulletin"),
    ]
    return SourcesResponse(sources=items, as_of=datetime.now(timezone.utc))

@router.head("/sources")
async def head_sources(response: Response):
    return Response(status_code=200, headers={"Cache-Control": "public, max-age=300, no-transform"})
