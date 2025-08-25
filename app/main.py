from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.schemas import ErrorModel

def _err_json(request: Request, status: int, code: str, message: str, hint: str | None = None):
    req_id = getattr(getattr(request, "state", object()), "request_id", None) or "n/a"
    return JSONResponse(
        status_code=status,
        content=ErrorModel(code=code, message=message, request_id=req_id, hint=hint).model_dump(),
        headers={"x-request-id": req_id},
    )

def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")
    # 中间件：RequestId / ResponseTime / JsonErrorEnvelope / AccessLog / DefaultCacheControl（若有）
    from app.routers import meta, ports
    app.include_router(meta.router,  prefix="/v1",       tags=["meta"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])

    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        return _err_json(request, exc.status_code, f"http_{exc.status_code}", str(exc.detail or "HTTP error"))

    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        return _err_json(request, 500, "http_500", "Internal Server Error")

    return app

app = create_app()