import os
from fastapi import FastAPI
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
    app.include_router(meta.router,  prefix="/v1",        tags=["meta"])
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

    return app

app = create_app()
