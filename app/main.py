from __future__ import annotations

import os
import re
import uuid
from http import HTTPStatus
from typing import Optional, Set

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# --- Sentry（可选） ---
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05, integrations=[FastAPIIntegration()])
    except Exception:
        pass

# --- 外部中间件（有则用） ---
try:
    from app.middlewares.request_id import RequestIdMiddleware as ExternalRequestIdMw
except Exception:
    ExternalRequestIdMw = None

try:
    from app.middlewares.api_key import ApiKeyMiddleware as ExternalApiKeyMw
except Exception:
    ExternalApiKeyMw = None

from app.middlewares.rate_limit import RateLimitMiddleware
from app.openapi_extra import add_api_key_security


# ---------- 本地兜底中间件 ----------
class _LocalRequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        try:
            request.state.request_id = rid
        except Exception:
            pass
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response


class _LocalApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, valid_keys: Set[str], demo_key: Optional[str]):
        super().__init__(app)
        self.valid = set(k for k in (valid_keys or set()) if k)
        self.demo = demo_key
        # 精确放行的公共路径（无 API Key）
        self._public_paths = {
            "/", "/v1/health", "/openapi.json", "/docs", "/redoc", "/robots.txt",
            "/v1/meta/sources", "/v1/sources",
        }
        # 前缀放行：internal 管理端（由内部路由自行做管理员鉴权）
        self._public_prefixes = ("/internal/keys",)

    def _extract_key(self, request: Request) -> Optional[str]:
        try:
            hdrs = request.headers
            key = hdrs.get("x-api-key")
            if not key:
                auth = hdrs.get("authorization", "")
                if isinstance(auth, (bytes, bytearray)):
                    auth = auth.decode("utf-8", "ignore")
                if isinstance(auth, str) and auth.lower().startswith("bearer "):
                    key = auth[7:].strip()
            if isinstance(key, (bytes, bytearray)):
                key = key.decode("utf-8", "ignore")
            return (key or None)
        except Exception:
            return None

    async def dispatch(self, request: Request, call_next):
        # ✅ 修复点：放行所有预检请求，避免 CORS 预检被拦截成 401
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path or ""
        # 1) 完全匹配的公共路径
        if path in self._public_paths:
            return await call_next(request)
        # 2) 以 /internal/keys 开头的前缀，交由内部路由做管理员鉴权
        if any(path.startswith(p) for p in self._public_prefixes):
            return await call_next(request)

        # 其余路径仍需业务 API Key
        key = self._extract_key(request)
        if key and self.demo and key == self.demo and request.method.upper() in ("GET", "HEAD"):
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
                "hint": "Provide API key via 'X-API-Key' or 'Authorization: Bearer <key>'",
            },
        )


class _HealthBypassMiddleware(BaseHTTPMiddleware):
    """极早返回 /v1/health，避免被下游限流/鉴权拦截。"""
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/v1/health":
            from datetime import datetime, timezone
            rid = request.headers.get("x-request-id") or str(uuid.uuid4())
            return JSONResponse(
                status_code=200,
                headers={"x-request-id": rid},
                content={"ok": True, "ts": datetime.now(timezone.utc).isoformat()},
            )
        return await call_next(request)


class _CommonHeadersMiddleware(BaseHTTPMiddleware):
    """
    统一响应头：暴露关键头 + 默认缓存策略（并补齐 no-transform）
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Access-Control-Expose-Headers",
            "ETag, Content-Length, Content-Type, X-Request-ID",
        )
        cc = response.headers.get("Cache-Control")
        if not cc:
            response.headers["Cache-Control"] = "public, max-age=300, no-transform"
        elif "no-transform" not in cc.lower():
            response.headers["Cache-Control"] = f"{cc}, no-transform"
        return response


# --- UNLOCODE Guard Middleware（仅做格式校验，非法 422） ---
from starlette.middleware.base import BaseHTTPMiddleware as _BHM
from fastapi.responses import JSONResponse

_UNLOCODE_RE = re.compile(r"^[A-Z]{2}[A-Z2-9]{3}$")

class _PortsUnlocodeGuardMiddleware(_BHM):
    def __init__(self, app):
        super().__init__(app)
        self._prefixes = ("/v1/ports/",)

    async def dispatch(self, request, call_next):
        path = request.url.path or ""
        for pref in self._prefixes:
            if path.startswith(pref) and len(path) > len(pref):
                seg = path[len(pref):].split("/", 1)[0]
                if not _UNLOCODE_RE.match(seg.upper()):
                    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
                    return JSONResponse(
                        status_code=422,
                        headers={"x-request-id": rid},
                        content={
                            "code": "http_422",
                            "message": "invalid UN/LOCODE format",
                            "request_id": rid,
                            "hint": "expected pattern: ^[A-Z]{2}[A-Z2-9]{3}$"
                        },
                    )
                break
        return await call_next(request)


def _collect_keys() -> tuple[Set[str], Optional[str]]:
    demo_key = os.getenv("NEXT_PUBLIC_DEMO_API_KEY", "dev_demo_123").strip()
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    api_keys_env = os.getenv("API_KEYS", "")
    keys = set(k.strip() for k in api_keys_env.split(",") if k.strip())
    if admin_key:
        keys.add(admin_key)
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
            "  - Demo: header `X-API-Key: dev_demo_123`\n"
            "  - Production: `X-API-Key: <pp_xxx>` or `Authorization: Bearer <key>`\n"
        ),
    )

    # CORS（公开 API 建议 *）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["*", "X-API-Key", "Authorization"],
        expose_headers=["ETag", "Content-Length", "Content-Type", "X-Request-ID"],
        max_age=3600,
    )

    # 中间件顺序
    app.add_middleware(_HealthBypassMiddleware)
    if ExternalRequestIdMw:
        app.add_middleware(ExternalRequestIdMw)
    else:
        app.add_middleware(_LocalRequestIdMiddleware)
    app.add_middleware(_CommonHeadersMiddleware)

    # 鉴权（支持环境强制本地白名单）
    valid_keys, demo_key = _collect_keys()
    force_local = os.getenv("FORCE_LOCAL_APIKEY", "").strip().lower() in ("1", "true", "yes", "on")
    if ExternalApiKeyMw and not force_local:
        try:
            app.add_middleware(ExternalApiKeyMw)
        except Exception:
            app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)
    else:
        app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)

    if not os.getenv("DISABLE_RATELIMIT"):
        app.add_middleware(RateLimitMiddleware)

    # 路由
    from app.routers import meta, hs, alerts, ports, health  # noqa: E402
    app.include_router(meta.router)                         # /v1 + /v1/meta/sources + /v1/sources
    app.include_router(hs.router, prefix="/v1/hs", tags=["hs"])
    app.include_router(alerts.router, prefix="/v1", tags=["alerts"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])
    app.include_router(health.router)  # /v1/health

    # 内部密钥与 Stripe（如存在）
    try:
        from app.routers import internal_keys  # noqa: E402
        app.include_router(internal_keys.router)  # /internal/keys/...
    except Exception:
        pass
    try:
        from app.routers import stripe_webhook  # noqa: E402
        app.include_router(stripe_webhook.router)
    except Exception:
        pass

    # 可选 Trio 端点
    try:
        if os.getenv("ENABLE_PORTS_TRIO", "").strip().lower() in ("1", "true", "yes", "on"):
            from app.routers import ports_trio  # noqa: E402
            app.include_router(ports_trio.router, prefix="/v1/ports", tags=["ports"])
    except Exception:
        pass

    # Admin（可选）
    try:
        from app.routers import admin_backfill  # noqa: E402
        app.include_router(admin_backfill.router, prefix="/v1/admin", tags=["admin"])
    except Exception:
        pass

    # devportal（可选）
    try:
        if os.path.isdir("docs/devportal"):
            app.mount("/devportal", StaticFiles(directory="docs/devportal", html=True), name="devportal")
    except Exception:
        pass

    # 统一异常体
    def _request_id(req: Request) -> str:
        return req.headers.get("x-request-id") or str(uuid.uuid4())

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        rid = _request_id(request)
        return JSONResponse(
            status_code=422,
            headers={"x-request-id": rid},
            content={"code": "http_422", "message": "Validation Error", "request_id": rid, "hint": ""},
        )

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
                "hint": "",
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _starlette_http_exc(request: Request, exc: StarletteHTTPException):
        rid = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            headers={"x-request-id": rid},
            content={
                "code": f"http_{exc.status_code}",
                "message": str(exc.detail) if getattr(exc, "detail", None) else "Error",
                "request_id": rid,
                "hint": "",
            },
        )

    @app.exception_handler(Exception)
    async def _any_exc(request: Request, exc: Exception):
        rid = _request_id(request)
        return JSONResponse(
            status_code=500,
            headers={"x-request-id": rid},
            content={"code": "http_500", "message": "Internal Server Error", "request_id": rid, "hint": ""},
        )

    # UNLOCODE Guard（在路由之后也可生效）
    app.add_middleware(_PortsUnlocodeGuardMiddleware)

    # OpenAPI 安全声明
    add_api_key_security(app)

    return app


app = create_app()


@app.get("/")
async def root():
    return RedirectResponse(url="/v1/health", status_code=307)


# === OpenAPI schema whitelist + alias (contract-only) ===
from fastapi.openapi.utils import get_openapi

_OPENAPI_PATH_WHITELIST = {
    "/v1/health",
    "/v1/meta/sources",
    "/v1/sources",
    "/v1/ports/{unlocode}/overview",
    "/v1/ports/{unlocode}/trend",
    "/v1/ports/{unlocode}/snapshot",
    "/v1/ports/{unlocode}/dwell",
    "/v1/ports/{unlocode}/alerts",
    "/v1/hs/{hs_code}/imports",
}
_OPENAPI_ALIASES = {
    "/v1/hs/{code}/imports": "/v1/hs/{hs_code}/imports",
}

_cached_openapi_schema = None

def custom_openapi():
    """Contract-only OpenAPI: whitelist + alias, cached."""
    global _cached_openapi_schema
    if _cached_openapi_schema is not None:
        return _cached_openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=getattr(app, "description", None),
        routes=app.routes,
    )

    paths = schema.get("paths", {}) or {}
    filtered = {k: v for k, v in paths.items() if k in _OPENAPI_PATH_WHITELIST}

    import copy
    for alias, src in _OPENAPI_ALIASES.items():
        if src in filtered and alias not in filtered:
            filtered[alias] = copy.deepcopy(filtered[src])

    schema["paths"] = filtered
    _cached_openapi_schema = schema
    return _cached_openapi_schema

# 覆盖一次即可
app.openapi = custom_openapi  # type: ignore

# --- OpenAPI fixup: ensure /v1/hs/{code}/imports alias key is present ---
try:
    schema = app.openapi()
    if isinstance(schema, dict):
        paths = schema.get("paths", {}) or {}
        src = "/v1/hs/{hs_code}/imports"
        alias = "/v1/hs/{code}/imports"
        if src in paths and alias not in paths:
            paths[alias] = paths[src]
            schema["paths"] = paths
            app.openapi_schema = schema
except Exception:
    pass


# 兜底 OPTIONS（CORS 预检）
@app.options("/{full_path:path}")
async def _options_all(full_path: str):
    return JSONResponse(status_code=204, content=None)