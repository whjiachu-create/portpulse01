#!/usr/bin/env bash
set -euo pipefail

echo "== create git branch =="
git checkout -b fix/mw-etag-probe || true

# --- app/main.py ---
mkdir -p app
cat > app/main.py <<'PY'
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")

    from .middlewares import (
        RequestIdMiddleware,
        JsonErrorEnvelopeMiddleware,
        AccessLogMiddleware,
        DefaultCacheControlMiddleware,
        ResponseTimeHeaderMiddleware,
    )
    from .routers import meta, ports

    # 中间件顺序：请求ID → 耗时头 → 错误封装 → 默认缓存策略 → 访问日志
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)
    app.add_middleware(AccessLogMiddleware)

    # 路由
    app.include_router(meta.router,  prefix="/v1", tags=["meta"])
    app.include_router(ports.router, prefix="/v1", tags=["ports"])
    return app

app = create_app()
PY

# --- app/middlewares.py ---
cat > app/middlewares.py <<'PY'
from __future__ import annotations
import time, uuid, os, json, logging
from typing import Callable
from fastapi import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

# 用自定义 logger，避免 uvicorn.access 的格式器冲突
logger = logging.getLogger("app.access")

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Request-ID", rid)
        return resp

class JsonErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            from fastapi.exceptions import HTTPException
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
                detail = exc.detail
                etype = type(exc).__name__
            else:
                status_code = 500
                detail = "Internal Server Error"
                etype = type(exc).__name__
            payload = {
                "ok": False,
                "error": {"type": etype, "message": str(detail)},
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            rid = getattr(request.state, "request_id", None)
            if rid:
                payload["request_id"] = rid
            return Response(
                content=json.dumps(payload),
                status_code=status_code,
                media_type="application/json",
                headers={"Cache-Control": "no-store"},
            )

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.perf_counter()
        resp: Response = await call_next(request)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        client_ip = request.client.host if request.client else "-"
        ua = request.headers.get("user-agent", "-")
        rid = resp.headers.get("X-Request-ID", "-")
        logger.info('%s "%s %s" %s %.2fms "%s" %s',
                    client_ip, request.method, request.url.path,
                    resp.status_code, dur_ms, ua, rid)
        return resp

class DefaultCacheControlMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_policy: str = "public, max-age=300"):
        super().__init__(app)
        self.default_policy = default_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # /v1/health 恒定 no-store
        if request.url.path == "/v1/health":
            resp: Response = await call_next(request)
            resp.headers["Cache-Control"] = "no-store"
            return resp

        resp: Response = await call_next(request)
        # 仅 GET 成功响应且未显式设置时兜底
        if (request.method == "GET"
            and 200 <= resp.status_code < 300
            and "cache-control" not in {k.lower(): v for k, v in resp.headers.items()}):
            if request.url.path.startswith("/v1/"):
                resp.headers["Cache-Control"] = self.default_policy
        return resp

class ResponseTimeHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.perf_counter()
        resp: Response = await call_next(request)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        # 优先 Server-Timing，再兜底 X-Response-Time-ms
        resp.headers.setdefault("Server-Timing", f"app;dur={dur_ms:.0f}")
        resp.headers.setdefault("X-Response-Time-ms", f"{dur_ms:.0f}")

        # 版本探针，便于线上甄别是否跑的新代码
        resp.headers.setdefault("X-App-Commit", os.getenv("GIT_SHA", "dev"))
        resp.headers.setdefault("X-MW-Probe", "rt")
        return resp
PY

# --- app/routers/meta.py ---
mkdir -p app/routers
cat > app/routers/meta.py <<'PY'
from __future__ import annotations
from fastapi import APIRouter, Response, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import time

from app.dependencies import get_db_pool
from app.models import Source

router = APIRouter(tags=["meta"])

@router.get("/health")
async def health():
    # Railway gate 使用；必须总是 200 且 no-store
    return JSONResponse(content={"ok": True, "ts": time.time()},
                        headers={"Cache-Control": "no-store"})

@router.get("/sources", response_model=list[Source])
async def list_sources(response: Response, pool = Depends(get_db_pool)):
    rows = await pool.fetch(
        "SELECT id, name, url, last_updated FROM public.sources ORDER BY id;"
    )
    sources = [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat(),
        }
        for r in rows
    ]
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return sources
PY

# --- app/routers/ports.py ---
cat > app/routers/ports.py <<'PY'
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Literal, Set
from datetime import datetime, date
from fastapi import Request
import hashlib
import time

CSV_SOURCE_TAG = "ports:overview:strong-etag"  # 调试用标记

from ..dependencies import require_api_key, get_conn

router = APIRouter(tags=["ports"])

class Snapshot(BaseModel):
    snapshot_ts: datetime
    vessels: int
    avg_wait_hours: float
    congestion_score: float
    src: str
    src_loaded_at: datetime

class SnapshotResponse(BaseModel):
    unlocode: str
    snapshot: Optional[Snapshot] = None

class DwellPoint(BaseModel):
    date: date
    dwell_hours: float
    src: str

class DwellResponse(BaseModel):
    unlocode: str
    points: List[DwellPoint]

class OverviewSource(BaseModel):
    src: str
    src_loaded_at: datetime

class OverviewResponse(BaseModel):
    unlocode: str
    as_of: Optional[datetime] = None
    metrics: Optional[dict] = None
    source: Optional[OverviewSource] = None

class AlertItem(BaseModel):
    unlocode: str
    type: Literal["dwell_change"]
    window_days: int
    latest: float
    baseline: float
    change: float
    note: str

class AlertsResponse(BaseModel):
    unlocode: str
    window_days: int
    alerts: List[AlertItem]

class TrendPoint(BaseModel):
    date: date
    src: str
    vessels: Optional[int] = None
    avg_wait_hours: Optional[float] = None
    congestion_score: Optional[float] = None

class TrendResponse(BaseModel):
    unlocode: str
    days: int
    points: List[TrendPoint]

def _csv_line(values: List[str]) -> str:
    return ",".join(values) + "\n"

def _strong_etag_from_text(csv_text: str) -> str:
    digest = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    return f'"{digest}"'

def _client_etags(req: Request) -> Set[str]:
    inm = req.headers.get("if-none-match") or ""
    parts = [p.strip() for p in inm.split(",") if p.strip()]
    return set(parts)

def _etag_matches(strong_etag: str, client_tags: Set[str]) -> bool:
    def norm(t: str) -> str:
        t = t.strip()
        if t.startswith("W/"):
            t = t[2:].strip()
        return t
    norm_tags = {norm(t) for t in client_tags}
    return (strong_etag in norm_tags) or (strong_etag.strip('"') in {s.strip('"') for s in norm_tags})

@router.get("/{unlocode}/snapshot", summary="Port Snapshot")
async def port_snapshot(unlocode: str, _auth: None = Depends(require_api_key), conn=Depends(get_conn)):
    U = unlocode.upper()
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        U,
    )
    if not row:
        return SnapshotResponse(unlocode=U, snapshot=None)

    snap = Snapshot(
        snapshot_ts=row["snapshot_ts"],
        vessels=int(row["vessels"]),
        avg_wait_hours=float(row["avg_wait_hours"]),
        congestion_score=float(row["congestion_score"]),
        src=row["src"],
        src_loaded_at=row["src_loaded_at"],
    )
    return SnapshotResponse(unlocode=U, snapshot=snap)

@router.get("/{unlocode}/dwell", summary="Port Dwell")
async def port_dwell(
    unlocode: str,
    days: int = Query(14, ge=1, le=365),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    U = unlocode.upper()
    rows = await conn.fetch(
        """
        SELECT date, dwell_hours, src
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        U, days,
    )
    points = [DwellPoint(date=r["date"], dwell_hours=float(r["dwell_hours"]), src=r["src"]) for r in rows]
    return DwellResponse(unlocode=U, points=points)

@router.get("/{unlocode}/overview", summary="Port Overview")
async def port_overview(
    unlocode: str,
    request: Request,
    format: Literal["json", "csv"] = Query("json"),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    U = unlocode.upper()

    # 命中内存缓存（仅 CSV）
    if format == "csv":
        cache_key = f"overview_csv:{U}"
        if hasattr(request.app.state, 'cache'):
            cached = request.app.state.cache.get(cache_key)
            if cached:
                etag = _strong_etag_from_text(cached["content"])
                if _etag_matches(etag, _client_etags(request)):
                    return Response(
                        status_code=304,
                        headers={
                            "ETag": etag,
                            "Cache-Control": "public, max-age=300, no-transform",
                            "Vary": "Accept-Encoding",
                            "X-CSV-Source": CSV_SOURCE_TAG,
                        },
                    )
                return PlainTextResponse(
                    content=cached["content"],
                    media_type="text/csv; charset=utf-8",
                    headers={
                        "ETag": etag,
                        "Cache-Control": "public, max-age=300, no-transform",
                        "Vary": "Accept-Encoding",
                        "X-CSV-Source": CSV_SOURCE_TAG,
                    },
                )

    t0 = time.time()
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        U,
    )

    if format == "csv":
        header = _csv_line(["unlocode", "as_of", "vessels", "avg_wait_hours", "congestion_score"])
        if not row:
            body = _csv_line([U, "", "", "", ""])
        else:
            body = _csv_line([
                U,
                row["snapshot_ts"].isoformat(),
                str(int(row["vessels"])),
                f"{float(row['avg_wait_hours']):.2f}",
                f"{float(row['congestion_score']):.1f}",
            ])
        csv_text = header + body

        etag = _strong_etag_from_text(csv_text)
        if _etag_matches(etag, _client_etags(request)):
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=300, no-transform",
                    "Vary": "Accept-Encoding",
                    "X-CSV-Source": CSV_SOURCE_TAG,
                }
            )

        # 仅当生成耗时>800ms时缓存60s
        cost = time.time() - t0
        if cost > 0.8:
            if not hasattr(request.app.state, 'cache'):
                request.app.state.cache = {}
            request.app.state.cache[f"overview_csv:{U}"] = {
                "content": csv_text,
                "etag": etag,
                "ts": time.time(),
            }
            # 简单清理
            for k, v in list(request.app.state.cache.items()):
                if isinstance(v, dict) and "ts" in v and time.time() - v["ts"] > 60:
                    del request.app.state.cache[k]

        return PlainTextResponse(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
                "X-CSV-Source": CSV_SOURCE_TAG,
            }
        )

    # JSON
    if not row:
        return OverviewResponse(unlocode=U, as_of=None, metrics=None, source=None)
    return OverviewResponse(
        unlocode=U,
        as_of=row["snapshot_ts"],
        metrics={
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
        },
        source=OverviewSource(
            src=row["src"],
            src_loaded_at=row["src_loaded_at"],
        ),
    )

@router.get("/{unlocode}/alerts", summary="Port Alerts")
async def port_alerts(
    unlocode: str,
    window: str = Query("14d"),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    U = unlocode.upper()
    try:
        days = int(window.rstrip("dD"))
    except Exception:
        raise HTTPException(status_code=422, detail="window must like '14d'")

    rows = await conn.fetch(
        """
        SELECT date, dwell_hours
        FROM port_dwell
        WHERE unlocode = $1
          AND date >= CURRENT_DATE - $2::int
        ORDER BY date ASC
        """,
        U, days,
    )
    vals = [float(r["dwell_hours"]) for r in rows]
    if len(vals) < 2:
        return AlertsResponse(unlocode=U, window_days=days, alerts=[])

    mid = max(1, len(vals) // 2)
    baseline = sum(vals[:mid]) / len(vals[:mid])
    latest = sum(vals[mid:]) / len(vals[mid:])
    change = latest - baseline

    return AlertsResponse(
        unlocode=U, window_days=days, alerts=[
            AlertItem(
                unlocode=U,
                type="dwell_change",
                window_days=days,
                latest=round(latest, 2),
                baseline=round(baseline, 2),
                change=round(change, 2),
                note="Δ = latest - baseline",
            )
        ]
    )

@router.get("/{unlocode}/trend", summary="Port Trend", response_model=TrendResponse)
async def port_trend(
    unlocode: str,
    days: int = Query(180, ge=7, le=365),
    format: Literal["json", "csv"] = "json",
    fields: Optional[str] = Query(None),
    tz: str = Query("UTC"),
    limit: int = Query(365, ge=1, le=3650),
    offset: int = Query(0, ge=0, le=100000),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    U = unlocode.upper()
    allowed = {"vessels", "avg_wait_hours", "congestion_score"}
    if fields:
        req = [f.strip() for f in fields.split(",") if f.strip()]
        use_fields = [f for f in req if f in allowed] or list(allowed)
    else:
        use_fields = list(allowed)

    rows = await conn.fetch(
        f"""
        WITH daily AS (
          SELECT
            (snapshot_ts AT TIME ZONE 'UTC')::date AS d,
            FIRST_VALUE(vessels) OVER w AS vessels,
            FIRST_VALUE(avg_wait_hours) OVER w AS avg_wait_hours,
            FIRST_VALUE(congestion_score) OVER w AS congestion_score,
            FIRST_VALUE(src) OVER w AS src
          FROM port_snapshots
          WHERE unlocode = $1
            AND snapshot_ts >= (CURRENT_DATE - $2::int)
          WINDOW w AS (PARTITION BY (snapshot_ts AT TIME ZONE 'UTC')::date ORDER BY snapshot_ts DESC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
        )
        SELECT DISTINCT ON (d) d AS date, vessels, avg_wait_hours, congestion_score, src
        FROM daily
        ORDER BY date DESC
        LIMIT $3 OFFSET $4
        """,
        U, days, limit, offset,
    )

    points = []
    for r in sorted(rows, key=lambda x: x["date"]):
        p = TrendPoint(
            date=r["date"],
            src=r["src"],
            vessels=int(r["vessels"]) if "vessels" in use_fields and r["vessels"] is not None else None,
            avg_wait_hours=float(r["avg_wait_hours"]) if "avg_wait_hours" in use_fields and r["avg_wait_hours"] is not None else None,
            congestion_score=float(r["congestion_score"]) if "congestion_score" in use_fields and r["congestion_score"] is not None else None,
        )
        points.append(p)

    if format == "csv":
        header = ["date"] + use_fields + ["src"]
        buf = _csv_line(header)
        for p in points:
            vals = [p.date.isoformat()]
            for f in use_fields:
                v = getattr(p, f)
                vals.append("" if v is None else str(v))
            vals.append(p.src)
            buf += _csv_line(vals)
        return PlainTextResponse(content=buf, media_type="text/csv; charset=utf-8",
                                 headers={"Cache-Control": "public, max-age=300"})

    return TrendResponse(unlocode=U, days=days, points=points)
PY

# --- scripts/start_with_gate.sh ---
mkdir -p scripts
cat > scripts/start_with_gate.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
export PORT="${PORT:-8080}"
export HOST="0.0.0.0"

UVICORN_CMD="uvicorn app.main:app --host ${HOST} --port ${PORT}"
echo "[start] ${UVICORN_CMD}"
exec ${UVICORN_CMD}
SH
chmod +x scripts/start_with_gate.sh

echo "== git add/commit =="
git add app scripts || true
git commit -m "fix: ensure new middlewares load + strong ETag for CSV + start script points to app.main:app" || true

echo "✅ Done. Now: run local verify or push to Railway."
