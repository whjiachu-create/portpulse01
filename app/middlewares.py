from __future__ import annotations
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp
import json
import logging

logger = logging.getLogger(__name__)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

class ResponseTimeHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["Server-Timing"] = f'app;dur={process_time*1000:.2f}'
        response.headers["X-Response-Time-ms"] = f"{process_time*1000:.2f}"
        return response

class JsonErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            return PlainTextResponse(
                content=json.dumps({"error": str(e)}, ensure_ascii=False),
                status_code=500,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )

class DefaultCacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 对于健康检查端点，强制no-store
        if request.url.path == "/v1/health":
            response.headers["Cache-Control"] = "no-store"
        # 对于其他2xx GET响应，如果没有显式Cache-Control，则设置默认值
        elif request.method == "GET" and 200 <= response.status_code < 300:
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "public, max-age=300"
                
        return response

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        
        logger.info(
            f'{request.state.request_id} '
            f'"{request.method} {request.url.path}" '
            f'{response.status_code} '
            f'{process_time*1000:.2f}ms'
        )
        
        return response
# --- Request ID middleware (P0) ---
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Populate request.state.request_id and mirror to 'x-request-id' header."""
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        resp: Response = await call_next(request)
        resp.headers["x-request-id"] = rid
        return resp
