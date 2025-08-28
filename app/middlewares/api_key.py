from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """非侵入式：只把 X-API-Key 暴露到 request.state.api_key，不做拦截。"""
    async def dispatch(self, request: Request, call_next):
        request.state.api_key = request.headers.get("x-api-key")
        return await call_next(request)
