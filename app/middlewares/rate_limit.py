import os, time
from typing import Callable, Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

# 可配：通过环境变量覆盖，默认 60 req / 60s
WINDOW = int(os.getenv("RATE_WINDOW", "60"))   # seconds
LIMIT  = int(os.getenv("RATE_LIMIT",  "60"))   # requests per window

# 永远放行的路径（健康/文档/首页）
SAFE_PATHS = {
    "/v1/health", "/", "/openapi.json", "/docs", "/redoc", "/robots.txt",
}

class _Bucket:
    __slots__ = ("window_start", "count")
    def __init__(self): self.window_start = 0; self.count = 0

def _client_ip(request: Request) -> str:
    # 先读代理头（Cloudflare / 常规反代）
    ip = request.headers.get("cf-connecting-ip") \
         or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return ip or "0.0.0.0"

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit:int=LIMIT, window:int=WINDOW):
        super().__init__(app)
        self.limit  = max(1, limit)
        self.window = max(1, window)
        self.buckets: Dict[Tuple[str,str], _Bucket] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        # 旁路：健康与文档不受限
        if request.url.path in SAFE_PATHS:
            return await call_next(request)

        try:
            key = (request.headers.get("x-api-key","")[:64], _client_ip(request))
            now = int(time.time())
            b = self.buckets.get(key)
            if b is None:
                b = _Bucket(); b.window_start = now; b.count = 0
            if now - b.window_start >= self.window:
                b.window_start = now; b.count = 0
            b.count += 1
            self.buckets[key] = b

            if b.count > self.limit:
                retry = max(1, b.window_start + self.window - now)
                rid = request.headers.get("x-request-id", "")
                return JSONResponse(
                    status_code=429,  # 标准码
                    headers={"Retry-After": str(retry), **({"x-request-id": rid} if rid else {})},
                    content={
                        "code": "rate_limited",
                        "message": "Too many requests",
                        "request_id": rid or None,
                        "hint": f"Try again in {retry}s (limit={self.limit}/{self.window}s).",
                    },
                )
            # 放行
            return await call_next(request)
        except Exception:
            # 出错也不要影响主流程（限流永不导致 500）
            return await call_next(request)
