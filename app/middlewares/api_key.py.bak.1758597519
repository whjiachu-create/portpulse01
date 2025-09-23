# app/middlewares/api_key.py
import os
import uuid
from typing import Optional, Set, Iterable, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

def _split_csv(v: str) -> List[str]:
    return [x.strip() for x in v.split(",") if x and x.strip()]

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    支持：
      - 头: X-API-Key: <key>  或  Authorization: Bearer <key>
      - 模式:
          PP_AUTH_MODE=strict  (默认, 只认白名单完整 key)
          PP_AUTH_MODE=prefix  (接受指定前缀的 key)
          PP_AUTH_MODE=off     (关闭鉴权, 仅本地调试)
      - 演示 key (仅 GET 放行):
          NEXT_PUBLIC_DEMO_API_KEY / PP_DEMO_KEY (默认 dev_demo_123)
      - 完整 key 白名单:
          ADMIN_API_KEY (单个)
          API_KEYS      (逗号分隔多个)
      - 前缀白名单：
          PP_ACCEPT_PREFIXES / PORTPULSE_ACCEPT_PREFIXES (逗号分隔，如 "pp_live_,pp_admin_,pp_dev_")
      - 永久放行路径: /, /v1/health, /openapi.json, /docs, /redoc, /robots.txt
    统一 401 错误体并透传/生成 x-request-id。
    """

    def __init__(
        self,
        app,
        header_name: str = "x-api-key",
        header_names: Optional[Iterable[str]] = None,
        **kwargs
    ):
        super().__init__(app)

        # 模式：strict / prefix / off
        self.mode = (os.getenv("PP_AUTH_MODE") or "strict").strip().lower()

        # demo key（GET-only）
        self.demo_key: Optional[str] = (
            os.getenv("PP_DEMO_KEY")
            or os.getenv("NEXT_PUBLIC_DEMO_API_KEY")
            or "dev_demo_123"
        ).strip()

        # 完整 key 白名单
        admin_key = (os.getenv("ADMIN_API_KEY") or "").strip()
        keys_env = os.getenv("API_KEYS", "")
        keys: Set[str] = set(_split_csv(keys_env))
        if admin_key:
            keys.add(admin_key)
        self.valid_keys: Set[str] = keys

        # 前缀白名单（prefix 模式用）
        prefixes_env = (
            os.getenv("PP_ACCEPT_PREFIXES")
            or os.getenv("PORTPULSE_ACCEPT_PREFIXES")
            or ""
        )
        self.accept_prefixes: List[str] = _split_csv(prefixes_env)

        # 支持多个 header 名
        names = list(header_names) if header_names else [header_name]
        self._header_names = [h.lower() for h in names]

        # 永远放行的路径
        self.public_paths = {"/", "/v1/health", "/openapi.json", "/docs", "/redoc", "/robots.txt"}

    def _get_key(self, request: Request) -> Optional[str]:
        hdrs = {k.decode().lower(): v.decode() for k, v in request.scope.get("headers", [])}
        # 多 header 尝试
        for hn in self._header_names:
            if hn in hdrs:
                return hdrs[hn]
        # Authorization: Bearer <key>
        auth = hdrs.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def _is_allowed(self, key: Optional[str], method: str) -> bool:
        # 关闭鉴权（仅限本地调试）
        if self.mode == "off":
            return True

        # demo key 只允许 GET
        if key and self.demo_key and key == self.demo_key and method == "GET":
            return True

        # 严格模式：完整 key 白名单
        if self.mode == "strict":
            return bool(key and key in self.valid_keys)

        # 前缀模式：完整 key 白名单 或 合法前缀
        if self.mode == "prefix":
            if key and key in self.valid_keys:
                return True
            if key and self.accept_prefixes:
                for p in self.accept_prefixes:
                    if key.startswith(p):
                        return True
        return False

    async def dispatch(self, request: Request, call_next):
        key = self._get_key(request)
        try:
            request.state.api_key = key
        except Exception:
            pass

        # 公开资源 + 预检
        if request.method.upper() == "OPTIONS" or request.url.path in self.public_paths:
            return await call_next(request)

        if self._is_allowed(key, request.method.upper()):
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