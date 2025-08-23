from fastapi import FastAPI
from contextlib import asynccontextmanager
from .services.deps import init_db_pool, close_db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(lifespan=lifespan)

# 中间件注册保持正确顺序
from .middlewares import (
    RequestIdMiddleware,
    ResponseTimeHeaderMiddleware,
    JsonErrorEnvelopeMiddleware,
    DefaultCacheControlMiddleware,
    AccessLogMiddleware
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(ResponseTimeHeaderMiddleware)
app.add_middleware(JsonErrorEnvelopeMiddleware)
app.add_middleware(DefaultCacheControlMiddleware)
app.add_middleware(AccessLogMiddleware)

# 路由注册
from .routers.meta import router as meta_router
from .routers.ports import router as ports_router
app.include_router(meta_router,  prefix="/v1",       tags=["meta"])
app.include_router(ports_router, prefix="/v1/ports", tags=["ports"])