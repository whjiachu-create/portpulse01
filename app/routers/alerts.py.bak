from fastapi import APIRouter, Query, Response, Request
from datetime import date, timedelta, datetime, timezone
from typing import List, Optional, Tuple
from hashlib import sha256
import json

# 计算服务（保持你的现有签名）
from app.services.alerts import compute_alerts, SeriesPoint

router = APIRouter(tags=["alerts"])

# =========================
# helpers
# =========================
def _stable_int_from_str(s: str, mod: int) -> int:
    """稳定整数：避免内置 hash 的随机盐，保证不同进程/时间一致。"""
    h = sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % mod

def _parse_window_tolerant(window_q: Optional[str]) -> int:
    """
    接受 '14' 或 '14d'。默认 14，范围 [7,60]。
    """
    if window_q is None:
        w = 14
    else:
        s = str(window_q).strip().lower()
        if s.endswith("d"):
            s = s[:-1]
        try:
            w = int(s)
        except Exception:
            w = 14
    if w < 7:
        w = 7
    if w > 60:
        w = 60
    return w

def _bucket_now_utc(minutes: int = 5) -> datetime:
    """把当前时间对齐到 5 分钟桶，用于稳定 ETag。"""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    bm = (now.minute // minutes) * minutes
    return now.replace(minute=bm, second=0)

def _json_body_and_headers(payload: dict) -> Tuple[bytes, dict]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = '"' + sha256(body).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Content-Type": "application/json; charset=utf-8",
        "Vary": "Accept-Encoding",
    }
    return body, headers

def _maybe_304(request: Request, headers: dict) -> Optional[Response]:
    inm = request.headers.get("if-none-match")
    if not inm:
        return None
    cands = [s.strip() for s in inm.split(",")]
    if headers["ETag"] in cands or f'W/{headers["ETag"]}' in cands:
        return Response(status_code=304, headers=headers)
    return None

# —— demo 序列（稳定可复现）——
def _demo_dwell_series(unlocode: str, window: int) -> List[SeriesPoint]:
    base = 24 + _stable_int_from_str(unlocode.upper(), 7)  # 24~30 的基线
    today = date.today()
    pts: List[SeriesPoint] = []
    for i in range(window):
        d = today - timedelta(days=window - i)
        val = float(base + ((i * 7) % 6))  # 小幅波动
        # 对 USLAX/USNYC 后半段做轻微抬升，方便演示告警
        if unlocode.upper() in {"USLAX", "USNYC"} and i > window // 2:
            val += 2.5
        pts.append(SeriesPoint(d=d, v=val))
    return pts

# =========================
# routes
# =========================
@router.get("/ports/{unlocode}/alerts", summary="Dwell change alerts (v1)")
async def get_alerts(
    unlocode: str,
    request: Request,
    response: Response,
    window: Optional[str] = Query("14", description="支持 '14' 或 '14d'，范围 7-60"),
):
    """
    返回 JSON；加 Cache-Control、稳定 ETag；支持 If-None-Match→304。
    """
    w = _parse_window_tolerant(window)
    # TODO: 上线后接 ETL/DB；当前用 demo 保证验收可测
    series = _demo_dwell_series(unlocode, w)

    # 计算告警（沿用你的服务函数）
    alerts = compute_alerts(series, w)

    payload = {
        "unlocode": unlocode.upper(),
        "window_days": w,
        "items": [
            {
                "date": a.date.isoformat() if hasattr(a.date, "isoformat") else str(a.date),
                "metric": a.metric,
                "delta": a.delta,
                "severity": a.severity,
                "explain": getattr(a, "explain", None),
            }
            for a in alerts
        ],
        # 为 ETag 稳定增加“桶时间戳”（与 ports/meta 一致 5min）
        "_as_of_bucket": _bucket_now_utc(5).isoformat(),
        "_src": "demo",
    }

    body, headers = _json_body_and_headers(payload)
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe

    # 透传缓存头到响应（FastAPI 默认会写自己的 Content-Type，这里我们覆盖）
    for k, v in headers.items():
        response.headers[k] = v
    return Response(content=body, headers=headers)

@router.head("/ports/{unlocode}/alerts", summary="HEAD for alerts (v1)")
async def head_alerts(
    unlocode: str,
    request: Request,
    window: Optional[str] = Query("14", description="支持 '14' 或 '14d'，范围 7-60"),
):
    w = _parse_window_tolerant(window)
    series = _demo_dwell_series(unlocode, w)
    # 与 GET 生成相同的 payload（不返回 body，只产出相同头部）
    payload = {
        "unlocode": unlocode.upper(),
        "window_days": w,
        "items": [],  # HEAD 不关心内容，但参与 ETag 的字段应与 GET 对齐
        "_as_of_bucket": _bucket_now_utc(5).isoformat(),
        "_src": "demo",
    }
    body, headers = _json_body_and_headers(payload)
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(status_code=200, headers=headers)
