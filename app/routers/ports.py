# app/routers/ports.py
from fastapi import APIRouter, Depends, Query
from app.deps import require_api_key, get_conn

router = APIRouter()

@router.get("/{unlocode}/snapshot", summary="Port Snapshot", tags=["ports"])
async def port_snapshot(unlocode: str, _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    # ... 保持你原有实现 ...
    ...

@router.get("/{unlocode}/dwell", summary="Port Dwell", tags=["ports"])
async def port_dwell(unlocode: str, days: int = Query(30, ge=1, le=365),
                     _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    # ... 保持你原有实现 ...
    ...

@router.get("/{unlocode}/overview", summary="Port Overview", tags=["ports"])
async def port_overview(unlocode: str, format: str = "json",
                        _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    # ... 保持你原有实现 ...
    ...

@router.get("/{unlocode}/alerts", summary="Port Alerts", tags=["ports"])
async def port_alerts(unlocode: str, window: str = "14d",
                      _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    # ... 保持你原有实现 ...
    ...

@router.get("/{unlocode}/trend", summary="Port Trend", tags=["ports"])
async def port_trend(unlocode: str, days: int = Query(180, ge=7, le=365),
                     format: str = "json", fields: str | None = None, tz: str = "UTC",
                     limit: int = Query(365, ge=1, le=3650), offset: int = Query(0, ge=0, le=100000),
                     _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    # ... 保持你原有实现 ...
    ...