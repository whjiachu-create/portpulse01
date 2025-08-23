from fastapi import FastAPI
# Delete:from app.routers import meta, ports

# Delete:app = FastAPI()

# Delete:app.include_router(meta.router, prefix="/v1", tags=["meta"])
# Delete:app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])

# Delete:# Routers
# Delete:from app.routers import ports, health

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
    from app.routers import meta, ports
    app.include_router(meta.router, prefix="/v1", tags=["meta"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])

    # Middleware order: ID → Timing → Error envelope → Access log → Default cache
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ResponseTimeHeaderMiddleware)
    app.add_middleware(JsonErrorEnvelopeMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(DefaultCacheControlMiddleware)

    return app


app = create_app()
