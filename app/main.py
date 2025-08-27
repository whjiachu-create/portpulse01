import os
from fastapi import FastAPI
import os
try:
    import sentry_sdk
    SENTRY_DSN=os.getenv('SENTRY_DSN')
    if SENTRY_DSN:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.05, integrations=[FastApiIntegration()])
except Exception:
    pass
from fastapi.staticfiles import StaticFiles

# 中间件（Request-ID 如已有可保留）
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

    if RequestIdMiddleware:
        app.add_middleware(RequestIdMiddleware)

    # —— 路由统一在 create_app 内挂载，确保被 OpenAPI 收录 ——
    from app.routers import meta, hs, alerts, ports  # noqa

    # /v1/sources 等
    app.include_router(meta.router)  # 确保包含meta路由
    # /v1/hs/{code}/imports
    app.include_router(hs.router,    prefix="/v1/hs",     tags=["hs"])
    # /v1/ports/{unlocode}/alerts
    app.include_router(alerts.router, prefix="/v1",       tags=["alerts"])
    # /v1/ports/{unlocode}/(trend|dwell|snapshot)
    app.include_router(ports.router, prefix="/v1/ports",  tags=["ports"])

    # /devportal 静态站（存在才挂，避免生产报错）
    try:
        if os.path.isdir("docs/devportal"):
            app.mount("/devportal", StaticFiles(directory="docs/devportal", html=True), name="devportal")
    except Exception:
        pass

    
    from app.routers import ports_trio  # new P1 trio
    app.include_router(ports_trio.router, prefix="/v1/ports", tags=["ports"])

    return app

app = create_app()


# --- unified_error_body ---
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from http import HTTPStatus
import uuid

def _request_id(req:Request)->str:
    rid=req.headers.get("x-request-id") or str(uuid.uuid4())
    return rid

@app.exception_handler(HTTPException)
async def _http_exc(request:Request, exc:HTTPException):
    rid=_request_id(request)
    return JSONResponse(status_code=exc.status_code,
                        headers={"x-request-id": rid},
                        content={"code": f"http_{exc.status_code}",
                                 "message": exc.detail or HTTPStatus(exc.status_code).phrase,
                                 "request_id": rid, "hint": None})

@app.exception_handler(Exception)
async def _any_exc(request:Request, exc:Exception):
    rid=_request_id(request)
    return JSONResponse(status_code=500,
                        headers={"x-request-id": rid},
                        content={"code": "http_500",
                                 "message": "Internal Server Error",
                                 "request_id": rid, "hint": None})
