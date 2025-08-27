from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os

_PUBLIC_PREFIXES = ("/v1/health", "/openapi.json", "/docs", "/redoc", "/favicon.ico")

class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.required = os.getenv("REQUIRE_API_KEY", "false").lower() in ("1","true","yes")
        self.keys = {k.strip() for k in os.getenv("API_KEYS","").split(",") if k.strip()}

    async def dispatch(self, request, call_next):
        path = request.url.path
        # 公共路径不校验
        if path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)

        # 未开启强制、或未配置密钥：直接放行（便于灰度）
        if not self.required or not self.keys:
            return await call_next(request)

        key = request.headers.get("x-api-key")
        if key and key in self.keys:
            return await call_next(request)

        rid = request.headers.get("x-request-id","")
        return JSONResponse(status_code=401, content={
            "code":"unauthorized",
            "message":"Missing or invalid API key",
            "request_id": rid
        })
