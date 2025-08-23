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
