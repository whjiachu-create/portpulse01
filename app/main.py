from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")

    from .middlewares import (
        RequestIdMiddleware,
        JsonErrorEnvelopeMiddleware,
        AccessLogMiddleware,
        DefaultCacheControlMiddleware,
        ResponseTimeHeaderMiddleware,
    )
    from .routers import meta, ports

    # 中间件顺序：请求ID → 耗时头 → 错误封装 → 默认缓存策略 → 访问日志
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)
    app.add_middleware(AccessLogMiddleware)

    # 路由
    app.include_router(meta.router,  prefix="/v1", tags=["meta"])
    app.include_router(ports.router, prefix="/v1", tags=["ports"])
    return app

app = create_app()
