# app/middlewares/api_key.py
import os
import uuid
from typing import Optional, Set, Iterable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    兼容两种头：
      - X-API-Key: <key>
      - Authorization: Bearer <key>
    约定：
      - 演示 key（NEXT_PUBLIC_DEMO_API_KEY，默认 dev_demo_123）仅放行 GET
      - 正式 key（ADMIN_API_KEY 或 API_KEYS 里逗号分隔）放行所有
      - /, /v1/health, /openapi.json, /docs, /redoc, /robots.txt 始终放行
    """

    def __init__(
        self,
        app,
        header_name: str = "x-api-key",
        header_names: Optional[Iterable[str]] = None,   # 新老 main.py 都可
        **kwargs,  # ← 关键：忽略未知参数，避免线上老代码崩
    ):
        super().__init__(app)

        self.demo_key: Optional[str] = os.getenv("NEXT_PUBLIC_DEMO_API_KEY", "dev_demo_123")

        admin_key = (os.getenv("ADMIN_API_KEY") or "").strip()
        keys_env = os.getenv("API_KEYS", "")
        keys: Set[str] = set(k.strip() for k in keys_env.split(",") if k.strip())
        if admin_key:
            keys.add(admin_key)
        self.valid_keys: Set[str] = keys

        names = list(header_names) if header_names else [header_name]
        self._header_names = [h.lower() for h in names]

        self.public_paths = {"/", "/v1/health", "/openapi.json", "/docs", "/redoc", "/robots.txt"}

    def _get_key(self, request: Request) -> Optional[str]:
        hdrs = {k.decode().lower(): v.decode() for k, v in request.scope.get("headers", [])}
        for hn in self._header_names:
            if hn in hdrs and hdrs[hn]:
                return hdrs[hn]
        auth = hdrs.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip() or None
        return None

    async def dispatch(self, request: Request, call_next):
        key = self._get_key(request)
        try:
            request.state.api_key = key
        except Exception:
            pass

        if request.method.upper() == "OPTIONS" or request.url.path in self.public_paths:
            return await call_next(request)

        # demo key 仅 GET
        if key and self.demo_key and key == self.demo_key and request.method.upper() == "GET":
            return await call_next(request)

        if key and key in self.valid_keys:
            return await call_next(request)

        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        return JSONResponse(
            status_code=401,
            headers={"x-request-id": rid},
            content={
                "code": "http_401",
                "message": "API key missing/invalid",
                "request_id": rid,
                "hint": "Use header 'x-api-key: <key>' or 'Authorization: Bearer <key>' (demo: dev_demo_123, prod: pp_admin_*/pp_live_*)",
            },
        )