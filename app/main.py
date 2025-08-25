from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Optional
from app.middlewares import RequestIdMiddleware
from app.routers import meta, ports, hs, alerts
def _err_json(request: Request, status: int, code: str, message: str, hint: Optional[str] = None):
    rid = getattr(request.state, "request_id", "n/a")
    return JSONResponse(status_code=status, content={"code": code, "message": message, "request_id": rid, "hint": hint})
def create_app() -> FastAPI:
    app = FastAPI(title="PortPulse API", version="1.0.0")
    app.add_middleware(RequestIdMiddleware)
    @app.exception_handler(StarletteHTTPException)
    async def http_ex_handler(request: Request, exc: StarletteHTTPException):
        return _err_json(request, exc.status_code, f"http_{exc.status_code}", str(getattr(exc, "detail", "HTTP error")))
    app.include_router(meta.router,  prefix="/v1",       tags=["meta"])
    app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])
    app.include_router(hs.router,    prefix="/v1/hs",    tags=["hs"])
    app.include_router(alerts.router, prefix="/v1",       tags=["alerts"])
    return app
app = create_app()
