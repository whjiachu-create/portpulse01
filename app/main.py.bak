from __future__ import annotations
import os
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Request, HTTPException
from typing import Optional, Set
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
        pass  # Sentry SDK 未安装时容错

# --- Middlewares & OpenAPI 安全声明 ---
from app.middlewares.rate_limit import RateLimitMiddleware
# 保持对你现有 ApiKeyMiddleware 的优先使用；如导入失败再用本地兜底
try:
    from app.middlewares.api_key import ApiKeyMiddleware as _ExternalApiKeyMw
except Exception:
    _ExternalApiKeyMw =Optional[str]

from app.openapi_extra import add_api_key_security
try:
    from app.middlewares.request_id import RequestIdMiddleware
except Exception:
    RequestIdMiddleware =Optional[str]  # 容错

# 本地轻量兜底：确保所有响应都带 x-request-id（不依赖外部文件）
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

# <<< 本地轻量兜底：API Key 校验（外部不可用时启用）
class _LocalApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, valid_keys: Set[str], demo_key: Optional[str]|Optional[str]):
        super().__init__(app)
        self.valid = set(k for k in (valid_keys or set()) if k)
        self.demo = demo_key

    async def dispatch(self, request: Request, call_next):
        # 取 key：支持 x-api-key 或 Authorization: Bearer
        key = request.headers.get("x-api-key")
        if not key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()

        # 放行无需鉴权的基础路由
        if request.url.path in ("/", "/v1/health", "/openapi.json", "/docs", "/redoc", "/robots.txt"):
            return await call_next(request)

        # 允许 demo key 访问 GET（演示用）
        if key and self.demo and key == self.demo and request.method.upper() == "GET":
            return await call_next(request)

        # 正式 key
        if key and key in self.valid:
            return await call_next(request)

        # 统一 401 错误体
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        return JSONResponse(
            status_code=401,
            headers={"x-request-id": rid},
            content={
                "code": "http_401",
                "message": "API key missing/invalid",
                "request_id": rid,
                "hint": "Provide API key via header: 'x-api-key: <key>' or 'Authorization: Bearer <key>'",
            },
        )
# >>>


def _collect_keys() -> tuple[Set[str], Optional[str]|Optional[str]]:
    """
    统一收集密钥：
    - NEXT_PUBLIC_DEMO_API_KEY（默认 dev_demo_123）
    - ADMIN_API_KEY（单个）
    - API_KEYS（逗号分隔）
    同时把关键变量写回环境，便于外部中间件读取。
    """
    demo_key = os.getenv("NEXT_PUBLIC_DEMO_API_KEY", "dev_demo_123")  # <<< 默认演示 key
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    api_keys_env = os.getenv("API_KEYS", "")
    keys = set(k.strip() for k in api_keys_env.split(",") if k.strip())
    if admin_key:
        keys.add(admin_key)

    # 写回环境，确保外部中间件可读取同一份配置
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
            "  - Production: set header `x-api-key: <pp_admin_xxx>` or "
            "`Authorization: Bearer <pp_admin_xxx>`\n"
        ),
    )

    # 统一 Request-ID：优先用外部中间件；否则使用本地兜底
    if RequestIdMiddleware:
        app.add_middleware(RequestIdMiddleware)
    else:
        app.add_middleware(_LocalRequestIdMiddleware)

    # --- 统一挂载 API Key 中间件 ---
    valid_keys, demo_key = _collect_keys()

    if _ExternalApiKeyMw is not Optional[str]:
        # 外部中间件（推荐）：若其支持关键字参数则传入；若不支持也能靠环境变量工作
        try:
            app.add_middleware(
                _ExternalApiKeyMw,
                header_name="X-API-Key",  # 允许两种传法
                token_prefixes=["Bearer "],                    # Authorization: Bearer
                demo_key=demo_key,
                valid_keys=valid_keys,
            )
        except TypeError:
            # 外部中间件不接受这些参数时，退化为仅靠环境变量
            app.add_middleware(_ExternalApiKeyMw)
    else:
        # 没有外部实现，用本地兜底
        app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)

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
                "hint":Optional[str],
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
                "hint":Optional[str],
            },
        )

    # OpenAPI 安全声明（你已有的工具函数）
    add_api_key_security(app)

    return app

app = create_app()

# Root route: redirect "/" to health check for a friendly landing
@app.get("/")
async def root():
    return RedirectResponse(url="/v1/health", status_code=307)

# 全局中间件
if not os.getenv("DISABLE_RATELIMIT"):
    app.add_middleware(RateLimitMiddleware)
# ApiKey 中间件已在 create_app 内处理（避免重复添加）
