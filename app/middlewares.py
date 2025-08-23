# app/middlewares.py
from __future__ import annotations
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

# 用自定义 logger，避免 uvicorn.access 的特定格式器报错
logger = logging.getLogger("app.access")

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        return response




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
        
        resp = await call_next(request)
        if (request.method == "GET"
            and 200 <= resp.status_code < 300
            and "cache-control" not in {k.lower(): v for k, v in resp.headers.items()}):
            path = request.url.path
            if path.startswith("/v1/") and path != "/v1/health":
                resp.headers["Cache-Control"] = self.default_policy
        return resp


class ResponseTimeHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        resp = await call_next(request)
        dur_ms = (time.perf_counter() - start) * 1000.0
        # 优先写 Server-Timing（代理保留概率更高）
        if "server-timing" not in {k.lower(): v for k, v in resp.headers.items()}:
            resp.headers["Server-Timing"] = f"app;dur={dur_ms:.0f}"
        # 兜底写 X-Response-Time-ms
        if "x-response-time-ms" not in {k.lower(): v for k, v in resp.headers.items()}:
            resp.headers["X-Response-Time-ms"] = f"{dur_ms:.0f}"
        return resp