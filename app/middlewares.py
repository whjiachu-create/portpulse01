# app/middlewares.py
from __future__ import annotations
import logging, time, uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# 简单访问日志记录器
logger = logging.getLogger("app.access")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

def _gen_id() -> str:
    return uuid.uuid4().hex[:12]

class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入/传递 X-Request-ID，并附带响应耗时。"""
    async def dispatch(self, request: Request, call_next: Callable):
        rid = request.headers.get("X-Request-ID") or _gen_id()
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # 确保异常路径也能写入响应头（随后由错误中间件包裹）
            response = Response(status_code=500)
            raise
        finally:
            dur_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-Ms"] = str(dur_ms)
        return response

class AccessLogMiddleware(BaseHTTPMiddleware):
    """轻量访问日志（method path status duration rid）。"""
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.perf_counter()
        response = await call_next(request)
        dur_ms = int((time.perf_counter() - start) * 1000)
        rid = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s %s %s ms rid=%s",
            request.method, request.url.path, response.status_code, dur_ms, rid
        )
        return response

class JsonErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    """统一错误包裹：确保始终返回 JSON，带 code/message/request_id。"""
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except RequestValidationError as e:
            rid = getattr(request.state, "request_id", _gen_id())
            msg = (e.errors()[0]["msg"] if e.errors() else "Validation error")
            return JSONResponse(
                {"code": "validation_error", "message": msg, "request_id": rid},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except StarletteHTTPException as e:
            rid = getattr(request.state, "request_id", _gen_id())
            detail = e.detail if isinstance(e.detail, str) else "HTTP error"
            return JSONResponse(
                {"code": f"http_error_{e.status_code}", "message": detail, "request_id": rid},
                status_code=e.status_code,
            )
        except Exception:
            rid = getattr(request.state, "request_id", _gen_id())
            logger.exception("Unhandled error rid=%s", rid)
            return JSONResponse(
                {"code": "internal_error", "message": "Internal Server Error", "request_id": rid},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

__all__ = ["RequestIdMiddleware", "AccessLogMiddleware", "JsonErrorEnvelopeMiddleware"]