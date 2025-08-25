from fastapi import APIRouter, Query, Response
from datetime import date

router = APIRouter(tags=["alerts"])

try:
    from app.schemas import AlertsResponse, AlertItem
except Exception:
    from pydantic import BaseModel
    from typing import List, Optional
    class AlertItem(BaseModel):
        date: date
        metric: str = "dwell_hours"
        delta: float
        severity: str = "info"
        explain: Optional[str] = None
    class AlertsResponse(BaseModel):
        unlocode: str
        window_days: int = 14
        items: List[AlertItem] = []

@router.get("/ports/{unlocode}/alerts", response_model=AlertsResponse, summary="Dwell change alerts (demo)")
async def get_alerts(unlocode: str, response: Response, window: int = Query(14, ge=7, le=60)):
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    items = []
    if unlocode in {"USLAX","USNYC"}:
        vals = [24 + (i % 6) for i in range(window)]
        baseline = sum(vals[: window//2]) / (window//2)
        latest = vals[-1]
        delta = float(round(latest - baseline, 2))
        sev = "high" if abs(delta) >= 3 else ("medium" if abs(delta) >= 1.5 else "low")
        items.append(AlertItem(date=date.today(), delta=delta, severity=sev, explain=f"Δ dwell vs baseline={baseline:.1f}h"))
    return AlertsResponse(unlocode=unlocode, window_days=window, items=items)
