from __future__ import annotations
import os
import uuid
from http import HTTPStatus
from typing import Optional, Set

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# --- Sentry（可选） ---
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05, integrations=[FastAPIIntegration()])
    except ImportError:
        pass

# --- Middlewares & OpenAPI ---
from app.middlewares.rate_limit import RateLimitMiddleware

# 优先使用项目里的 ApiKeyMiddleware；导入失败则置 None
try:
    from app.middlewares.api_key import ApiKeyMiddleware as ExternalApiKeyMw
except Exception:
    ExternalApiKeyMw = None  # <-- 用 None 作为兜底

from app.openapi_extra import add_api_key_security

try:
    from app.middlewares.request_id import RequestIdMiddleware
except Exception:
    RequestIdMiddleware = None  # <-- 同理

# 本地兜底：x-request-id
class _LocalRequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        try:
            request.state.request_id = rid
        except Exception:
            pass
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

# 本地兜底：API Key
class _LocalApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, valid_keys: Set[str], demo_key: Optional[str]):
        super().__init__(app)
        self.valid = set(k for k in (valid_keys or set()) if k)
        self.demo = demo_key

    async def dispatch(self, request: Request, call_next):
        key = request.headers.get("x-api-key")
        if not key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()

        if request.url.path in ("/", "/v1/health", "/openapi.json", "/docs", "/redoc", "/robots.txt"):
            return await call_next(request)

        if key and self.demo and key == self.demo and request.method.upper() == "GET":
            return await call_next(request)

        if key and key in self.valid:
            return await call_next(request)

        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        return JSONResponse(
            status_code=401,
            headers={"x-request-id": rid},
            content={
                "code": "http_401",
                "message": "API key missing/invalid",
                "request_id": rid,
                "hint": "Provide header 'x-api-key: <key>' or 'Authorization: Bearer <key>'",
            },
        )

def _collect_keys() -> tuple[Set[str], Optional[str]]:
    demo_key = os.getenv("NEXT_PUBLIC_DEMO_API_KEY", "dev_demo_123").strip()
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    api_keys_env = os.getenv("API_KEYS", "")

    keys = set(k.strip() for k in api_keys_env.split(",") if k.strip())
    if admin_key:
        keys.add(admin_key)

    # 回写环境，供外部中间件读取
    os.environ["NEXT_PUBLIC_DEMO_API_KEY"] = demo_key
    os.environ["API_KEYS"] = ",".join(sorted(keys))
    return keys, demo_key

def create_app() -> FastAPI:
    app = FastAPI(
        title="PortPulse API",
        version=os.getenv("APP_VERSION", "0.1.1"),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        description=(
            "Authentication:\n"
            "  - Demo: set header `x-api-key: dev_demo_123`\n"
            "  - Production: set header `x-api-key: <pp_admin_xxx>` or `Authorization: Bearer <pp_admin_xxx>`\n"
        ),
    )

    # Request-ID
    if RequestIdMiddleware:
        app.add_middleware(RequestIdMiddleware)
    else:
        app.add_middleware(_LocalRequestIdMiddleware)

    # API Key 中间件
    valid_keys, demo_key = _collect_keys()

    if ExternalApiKeyMw:
        # 先不带 kwargs（避免不同实现参数名不兼容）；若你后续确认实现支持，再加。
        try:
            app.add_middleware(ExternalApiKeyMw)
        except TypeError:
            # 极端情况下，退回到本地兜底
            app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)
    else:
        app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)

    # 路由
    from app.routers import meta, hs, alerts, ports
    app.include_router(meta.router)
    app.include_router(hs.router,     prefix="/v1/hs",    tags=["hs"])
    app.include_router(alerts.router, prefix="/v1",       tags=["alerts"])
    app.include_router(ports.router,  prefix="/v1/ports", tags=["ports"])

    try:
        from app.routers import ports_trio
        app.include_router(ports_trio.router, prefix="/v1/ports", tags=["ports"])
    except Exception:
        pass

    try:
        from app.routers import admin_backfill
        app.include_router(admin_backfill.router, prefix="/v1/admin", tags=["admin"])
    except Exception:
        pass

    try:
        from app.routers import internal_backfill
        app.include_router(internal_backfill.router, tags=["internal"])
    except Exception:
        pass

    try:
        if os.path.isdir("docs/devportal"):
            app.mount("/devportal", StaticFiles(directory="docs/devportal", html=True), name="devportal")
    except Exception:
        pass

    # 统一错误体
    def _request_id(req: Request) -> str:
        return req.headers.get("x-request-id") or str(uuid.uuid4())

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException):
        rid = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            headers={"x-request-id": rid},
            content={
                "code": f"http_{exc.status_code}",
                "message": exc.detail or HTTPStatus(exc.status_code).phrase,
                "request_id": rid,
                "hint": None,
            },
        )

    @app.exception_handler(Exception)
    async def _any_exc(request: Request, exc: Exception):
        rid = _request_id(request)
        return JSONResponse(
            status_code=500,
            headers={"x-request-id": rid},
            content={
                "code": "http_500",
                "message": "Internal Server Error",
                "request_id": rid,
                "hint": str(exc)[:200],  # 可选：便于排错
            },
        )

    add_api_key_security(app)
    return app

app = create_app()

@app.get("/")
async def root():
    return RedirectResponse(url="/v1/health", status_code=307)

# Rate limit 放最后
if not os.getenv("DISABLE_RATELIMIT"):
    app.add_middleware(RateLimitMiddleware)