from fastapi import FastAPI
from app.routers import meta, ports

app = FastAPI()

app.include_router(meta.router, prefix="/v1", tags=["meta"])
app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])


# Routers
from app.routers import ports, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="PortPulse API",
        description="API for port operations and vessel tracking",
        version="1.0.0"
    )

    # Middlewares
    from app.middlewares import (
        RequestIdMiddleware,
        ResponseTimeHeaderMiddleware,
        JsonErrorEnvelopeMiddleware,
        AccessLogMiddleware,
        DefaultCacheControlMiddleware,
    )

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])

    # Middleware order: ID → Timing → Error envelope → Access log → Default cache
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)

    return app


app = create_app()
