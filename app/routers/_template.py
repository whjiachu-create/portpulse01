from fastapi import APIRouter, Depends, Header, Query
from app.deps import require_api_key, get_conn

router = APIRouter()

@router.get("/{unlocode}/snapshot", summary="Port Snapshot", tags=["ports"])
async def port_snapshot(
    unlocode: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    _auth: None = Depends(require_api_key),
    conn = Depends(get_conn),
):
    ...