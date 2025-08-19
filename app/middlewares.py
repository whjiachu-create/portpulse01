# app/middlewares.py
from __future__ import annotations
import json, time, uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

JSON_CT = "application/json; charset=utf-8"

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.time()
        resp: Response = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        resp.headers["X-Response-Time-ms"] = str(int((time.time()-start)*1000))
        return resp

class JsonErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            rid = getattr(request.state, "request_id", "-")
            body = {
                "code": type(e).__name__,
                "message": str(e),
                "request_id": rid,
            }
            return Response(json.dumps(body), status_code=500, media_type=JSON_CT)

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.time()
        rid = getattr(request.state, "request_id", None) or "-"
        try:
            resp = await call_next(request)
            status = resp.status_code
        except Exception:
            status = 500
            raise
        finally:
            cost = int((time.time()-start)*1000)
            line = json.dumps({
                "lvl": "INFO",
                "rid": rid,
                "m": request.method,
                "path": request.url.path,
                "q": str(request.query_params),
                "status": status,
                "cost_ms": cost,
            })
            print(line, flush=True)
        return resp