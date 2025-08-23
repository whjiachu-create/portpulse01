from fastapi import FastAPI

# ✅ 推荐应用工厂，防止导入顺序问题
def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")

    from .middlewares import (
        RequestIdMiddleware, JsonErrorEnvelopeMiddleware, AccessLogMiddleware,
        DefaultCacheControlMiddleware, ResponseTimeHeaderMiddleware,
    )
    from .routers import meta, ports

    # 中间件顺序：ID → 耗时 → 错误包裹 → 默认缓存 → 访问日志（最后）
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)

    # 路由
    app.include_router(meta.router,  prefix="/v1", tags=["meta"])
    app.include_router(ports.router, prefix="/v1", tags=["ports"])
    return app

app = create_app()