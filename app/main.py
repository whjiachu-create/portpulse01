from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")

    # 中间件
    from .middlewares import (
        RequestIdMiddleware,
        ResponseTimeHeaderMiddleware,
        JsonErrorEnvelopeMiddleware,
        AccessLogMiddleware,
        DefaultCacheControlMiddleware,
    )

    # 路由（注意：必须同时导入 meta 和 ports）
    from .routers import meta
    from .routers import ports  # ⬅⬅⬅ 关键：导入 ports 模块

    # 中间件顺序：ID → 耗时 → 错误包裹 → 访问日志 → 默认缓存
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)

    # 路由挂载
    app.include_router(meta.router,  prefix="/v1",       tags=["meta"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])  # ⬅⬅⬅ 关键：真正把 ports 挂上来
    return app

app = create_app()
