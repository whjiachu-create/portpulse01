import os
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# --- Sentry（可选） ---
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05, integrations=[FastApiIntegration()])
except Exception:
    pass

# --- Middlewares & OpenAPI 安全声明 ---
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.api_key import ApiKeyMiddleware
from app.openapi_extra import add_api_key_security
try:
    from app.middlewares.request_id import RequestIdMiddleware
except Exception:
    RequestIdMiddleware = None  # 容错

def create_app() -> FastAPI:
    app = FastAPI(
        title="PortPulse API",
        version=os.getenv("APP_VERSION", "0.1.1"),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 可选的 Request-ID 中间件
    if RequestIdMiddleware:
        app.add_middleware(RequestIdMiddleware)

    # 路由（确保在 create_app 内 include，才能进 OpenAPI）
    from app.routers import meta, hs, alerts, ports  # noqa
    app.include_router(meta.router)                                # /v1/sources 等
    app.include_router(hs.router,     prefix="/v1/hs",    tags=["hs"])       # /v1/hs/{code}/imports
    app.include_router(alerts.router, prefix="/v1",       tags=["alerts"])   # /v1/ports/{unlocode}/alerts
    app.include_router(ports.router,  prefix="/v1/ports", tags=["ports"])    # /v1/ports/{unlocode}/trend|dwell|snapshot

    # P1 trio（如模块存在就挂载）
    try:
        from app.routers import ports_trio
        app.include_router(ports_trio.router, prefix="/v1/ports", tags=["ports"])
    except Exception:
        pass

    from app.routers import admin_backfill  # ← 新增
    app.include_router(admin_backfill.router, prefix="/v1/admin", tags=["admin"])  # ← 新增

    # 内部补采入口（如模块存在就挂载）
    try:
        from app.routers import internal_backfill
        app.include_router(internal_backfill.router, tags=["internal"])
    except Exception:
        pass

    # /devportal 静态站（存在才挂，避免生产报错）
    try:
        if os.path.isdir("docs/devportal"):
            app.mount("/devportal", StaticFiles(directory="docs/devportal", html=True), name="devportal")
    except Exception:
        pass

    # ---- 统一错误体 ----
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
                "hint": None,
            },
        )

    return app

app = create_app()
# 全局中间件
if not os.getenv("DISABLE_RATELIMIT"):
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiKeyMiddleware)     # 例：读取 API_KEYS/NEXT_PUBLIC_DEMO_API_KEY
add_api_key_security(app)
