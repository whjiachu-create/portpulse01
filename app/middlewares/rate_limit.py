import time
from typing import Callable, Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

Window = 60  # seconds
Limit = 60   # requests per window

class _Bucket:
    def __init__(self): self.window_start = 0; self.count = 0

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit:int=Limit, window:int=Window):
        super().__init__(app); self.limit=limit; self.window=window
        self.buckets: Dict[Tuple[str,str], _Bucket] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        key = request.headers.get("x-api-key","")[:64]
        ip  = request.client.host if request.client else "0.0.0.0"
        k   = (key, ip)
        now = int(time.time())
        b   = self.buckets.get(k) or _Bucket()
        if now - b.window_start >= self.window:
            b.window_start = now; b.count = 0
        b.count += 1
        self.buckets[k] = b
        if b.count > self.limit:
            retry = b.window_start + self.window - now
            return JSONResponse(
                status_code=403,
                headers={"Retry-After": str(max(1, retry))},
                content={"code":"rate_limited","message":"Too many requests","request_id": request.headers.get("x-request-id")}
            )
        return await call_next(request)
