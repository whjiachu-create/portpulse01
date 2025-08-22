# app/middlewares.py
from __future__ import annotations
import time, uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import Response
from typing import Callable
from fastapi import Request
import logging

logger = logging.getLogger("uvicorn.access")

# 请求 ID 中间件
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# 统一错误包装中间件（仅 JSON 错误）
class JsonErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            import json
            from fastapi.exceptions import HTTPException
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
                detail = exc.detail
            else:
                status_code = 500
                detail = "Internal Server Error"

            error_payload = {
                "ok": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(detail),
                },
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            }
            if hasattr(request.state, "request_id"):
                error_payload["request_id"] = request.state.request_id

            return Response(
                content=json.dumps(error_payload),
                status_code=status_code,
                media_type="application/json",
                headers={"Cache-Control": "no-store"},
            )

# 访问日志中间件
class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        formatted_time = f"{process_time * 1000:.2f}ms"

        client_ip = request.client.host if request.client else "-"
        method = request.method
        path = request.url.path
        status_code = response.status_code
        user_agent = request.headers.get("user-agent", "-")
        request_id = response.headers.get("X-Request-ID", "-")

        logger.info(
            f'{client_ip} "{method} {path}" {status_code} {formatted_time} "{user_agent}" {request_id}'
        )
        return response

# 限流中间件
class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, rpm: int = 120):
        super().__init__(app)
        self.rpm = rpm
        self.requests = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60

        if client_ip not in self.requests:
            self.requests[client_ip] = []

        # 清除窗口外的请求记录
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > window_start
        ]

        # 检查是否超过限制
        if len(self.requests[client_ip]) >= self.rpm:
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="Too Many Requests")

        # 记录当前请求
        self.requests[client_ip].append(now)

        return await call_next(request)

# 新增：兜底缓存控制中间件
class DefaultCacheControlMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, default_policy: str = "public, max-age=300, s-maxage=300"):
        super().__init__(app)
        self.default_policy = default_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 对 /v1/health 路径特殊处理，确保它总是返回 no-store
        if request.url.path == "/v1/health":
            resp: Response = await call_next(request)
            resp.headers["Cache-Control"] = "no-store"
            return resp
            
        resp: Response = await call_next(request)

        # 仅 GET 成功响应，且未显式设置时再兜底
        if (
            request.method == "GET"
            and 200 <= resp.status_code < 300
            and "cache-control" not in {k.lower(): v for k, v in resp.headers.items()}
        ):
            path = request.url.path
            # 只作用在我们 API 命名空间；且跳过 /v1/health
            if path.startswith("/v1/") and path != "/v1/health":
                resp.headers["Cache-Control"] = self.default_policy

        return resp
