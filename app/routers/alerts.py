from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, Response

router = APIRouter(tags=["alerts"])

# schemas（健壮导入）
try:
    from app.schemas import AlertsResponse, AlertItem
except Exception:
    from pydantic import BaseModel
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

# 计算服务
from app.services.alerts import compute_alerts, SeriesPoint

# —— 数据获取（当前阶段：若无 ETL，则提供稳定的 demo 序列，便于验收）——
def _demo_dwell_series(unlocode: str, window: int) -> List[SeriesPoint]:
    # 固定可复现：根据 unlocode 哈希产生稳定序列，USLAX/USNYC 略调权重方便出 alert
    base = abs(hash(unlocode)) % 10
    today = date.today()
    pts: List[SeriesPoint] = []
    for i in range(window):
        d = today - timedelta(days=window - i)
        val = 24 + base + ((i * 7) % 6)  # 24~30h 小幅波动
        if unlocode in {"USLAX", "USNYC"} and i > window//2:
            val += 2.5  # 制造轻微抬升，便于演示分位/变点
        pts.append(SeriesPoint(d=d, v=float(val)))
    return pts

@router.get("/ports/{unlocode}/alerts", response_model=AlertsResponse, summary="Dwell change alerts (v1)")
async def get_alerts(unlocode: str, response: Response, window: int = Query(14, ge=7, le=60)):
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"

    # TODO(数据接入后)：替换为真实 dwell 序列读取
    series = _demo_dwell_series(unlocode, window)

    alerts = compute_alerts(series, metric_name="dwell_hours")
    items = [
        AlertItem(date=a.date, metric=a.metric, delta=a.delta, severity=a.severity, explain=a.explain)
        for a in alerts
    ]
    return AlertsResponse(unlocode=unlocode, window_days=window, items=items)
