# --- safe imports / sentry 同前，保持不变 ---

from typing import Optional, Set

# ✅ 正确的导入兜底：用 None，而不是 Optional[str] 这种 typing 对象
try:
    from app.middlewares.api_key import ApiKeyMiddleware as ExternalApiKeyMw
except Exception:
    ExternalApiKeyMw = None  # type: ignore

try:
    from app.middlewares.request_id import RequestIdMiddleware
except Exception:
    RequestIdMiddleware = None  # type: ignore

# ✅ 本地 request-id 兜底
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

# ✅ 本地 API Key 兜底（签名简化，移除奇怪的联合类型写法）
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
                "hint": "Provide API key via header 'X-API-Key' or 'Authorization: Bearer <key>'",
            },
        )

def _collect_keys() -> tuple[Set[str], Optional[str]]:
    demo_key = os.getenv("NEXT_PUBLIC_DEMO_API_KEY", "dev_demo_123").strip()
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    keys = set(k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip())
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
            "  - Production: `X-API-Key: <pp_admin_xxx>` or `Authorization: Bearer <pp_admin_xxx>`\n"
        ),
    )

    # request-id
    if RequestIdMiddleware:
        app.add_middleware(RequestIdMiddleware)
    else:
        app.add_middleware(_LocalRequestIdMiddleware)

    # api-key
    valid_keys, demo_key = _collect_keys()
    if ExternalApiKeyMw:
        try:
            app.add_middleware(
                ExternalApiKeyMw,
                # 有的版本不接受这些 kw；失败则下方退化
                header_name="X-API-Key",
                token_prefixes=["Bearer "],
                demo_key=demo_key,
                valid_keys=valid_keys,
            )
        except TypeError:
            app.add_middleware(ExternalApiKeyMw)
    else:
        app.add_middleware(_LocalApiKeyMiddleware, valid_keys=valid_keys, demo_key=demo_key)

    # routers（与你现有保持一致）
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
    from app.routers import admin_backfill
    app.include_router(admin_backfill.router, prefix="/v1/admin", tags=["admin"])
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

    # 统一错误体（⚠️ hint 一律用 None，别再放 typing 对象）
    def _rid(req: Request) -> str:
        return req.headers.get("x-request-id") or str(uuid.uuid4())

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException):
        rid = _rid(request)
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
        rid = _rid(request)
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

    add_api_key_security(app)
    return app

app = create_app()

@app.get("/")
async def root():
    return RedirectResponse(url="/v1/health", status_code=307)

if not os.getenv("DISABLE_RATELIMIT"):
    app.add_middleware(RateLimitMiddleware)