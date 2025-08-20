# app/middlewares.py
from __future__ import annotations
import json
import logging
import time
import uuid
import contextvars
from typing import Callable, Awaitable
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# request_id 在任意位置可获取
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

def _first_ip(xff: str | None) -> str | None:
    if not xff:
        return None
    return xff.split(",")[0].strip()

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    为每个请求生成/透传 X-Request-Id，并注入到：
      - request.state.request_id
      - 上下文变量 request_id_var
      - 响应头 x-request-id
      - 响应头 x-response-time-ms
    """
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            # 确保上下文恢复
            request_id_var.reset(token)
        # 追加响应头
        try:
            dur_ms = int((time.perf_counter() - start) * 1000)
            response.headers["x-request-id"] = rid
            response.headers["x-response-time-ms"] = str(dur_ms)
        except Exception:
            pass
        return response

class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    结构化访问日志（单行 JSON），默认输出到 stdout。
    字段：ts, method, path, status, dur_ms, ip, ua, request_id
    """
    def __init__(self, app: ASGIApp, logger_name: str = "portpulse.access"):
        super().__init__(app)
        self.log = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        rid = getattr(request.state, "request_id", None) or request_id_var.get() or "-"
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            status = 500
            raise e
        finally:
            dur_ms = int((time.perf_counter() - start) * 1000)
            rec = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query,
                "status": status,
                "dur_ms": dur_ms,
                "ip": _first_ip(request.headers.get("x-forwarded-for")) or (request.client.host if request.client else None),
                "ua": request.headers.get("user-agent"),
                "request_id": rid,
            }
            try:
                self.log.info(json.dumps(rec, ensure_ascii=False))
            except Exception:
                # 日志失败不影响主流程
                pass
        return response