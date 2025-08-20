# app/middlewares.py
from __future__ import annotations
import contextvars, json, logging, time, uuid
from typing import Callable, Awaitable
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.requests import Request

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

def _first_ip(xff: str | None) -> str | None:
    if not xff:
        return None
    return xff.split(",")[0].strip()

class RequestIdASGIMiddleware:
    """更底层的 ASGI 中间件：保证所有响应都有 x-request-id / x-response-time-ms"""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        rid = None
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal rid
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                # 取请求上的 x-request-id；没有就生成
                if rid is None:
                    rid = uuid.uuid4().hex[:12]
                # 写入响应头
                dur_ms = int((time.perf_counter() - start) * 1000)
                headers += [
                    (b"x-request-id", rid.encode()),
                    (b"x-response-time-ms", str(dur_ms).encode()),
                ]
            await send(message)

        # 把 rid 放进上下文，供后续获取
        token = request_id_var.set(rid or uuid.uuid4().hex[:12])
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)

class AccessLogASGIMiddleware:
    """结构化访问日志（单行 JSON）"""
    def __init__(self, app: ASGIApp, logger_name: str = "portpulse.access"):
        self.app = app
        self.log = logging.getLogger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", status_code)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            dur_ms = int((time.perf_counter() - start) * 1000)
            headers = dict(scope.get("headers") or [])
            xff = headers.get(b"x-forwarded-for")
            ua = headers.get(b"user-agent")
            rec = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": scope["method"],
                "path": scope["path"],
                "query": scope.get("query_string", b"").decode(),
                "status": status_code,
                "dur_ms": dur_ms,
                "ip": _first_ip(xff.decode() if isinstance(xff, (bytes, bytearray)) else None),
                "ua": ua.decode() if isinstance(ua, (bytes, bytearray)) else None,
                "request_id": request_id_var.get(),
            }
            try:
                self.log.info(json.dumps(rec, ensure_ascii=False))
            except Exception:
                pass