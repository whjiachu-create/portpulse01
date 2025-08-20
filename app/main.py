# app/main.py
from __future__ import annotations
import logging, os
from typing import Any, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .middlewares import RequestIdASGIMiddleware, AccessLogASGIMiddleware, request_id_var
from app.routers import meta, ports, hs

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")

app = FastAPI(
    title="PortPulse & TradeMomentum API",
    description="PortPulse & TradeMomentum API",
    version="1.1",
)

# << 替换为 ASGI 级中间件 >>
app.add_middleware(RequestIdASGIMiddleware)
app.add_middleware(AccessLogASGIMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def _err_body(request: Request, code: str, message: str, status: int, *, hint: str | None = None, details: Any = None) -> JSONResponse:
    rid = request.headers.get("x-request-id") or request_id_var.get()
    body: Dict[str, Any] = {"code": code, "message": message, "request_id": rid}
    if hint:
        body["hint"] = hint
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content=body)

# —— 两套异常都兜住 —— #
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return _err_body(request, f"http_error_{exc.status_code}", msg, exc.status_code,
                     details=None if isinstance(exc.detail, str) else exc.detail)

@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return _err_body(request, f"http_error_{exc.status_code}", msg, exc.status_code,
                     details=None if isinstance(exc.detail, str) else exc.detail)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return _err_body(request, "validation_error", "Request validation failed", 422, details=exc.errors())

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("portpulse.app").exception("uncaught error: %r", exc)
    return _err_body(request, "internal_error", "Internal server error", 500)

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:  # 维持到 /docs
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/v1/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    db_err = getattr(app.state, "db_error", None)
    return {"ok": db_err is None, "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z", "db": None if db_err is None else str(db_err)}

# 动态装载路由（保持你现有逻辑）
def _include_router_if_exists(module_path: str, router_name: str, prefix: str, tags: list[str]):
    try:
        mod = __import__(module_path, fromlist=[router_name])
        app.include_router(getattr(mod, router_name), prefix=prefix, tags=tags)
    except Exception as e:
        logging.getLogger("portpulse.app").info("router skipped: %s (%s)", module_path, e)

_include_router_if_exists("app.routers.meta", "router", "/v1/meta", ["meta"])
_include_router_if_exists("app.routers.ports", "router", "/v1/ports", ["ports"])
_include_router_if_exists("app.routers.ports_extra", "router", "/v1/ports", ["ports"])
_include_router_if_exists("app.routers.hs", "router", "/v1", ["trade"])
# 其他 include_router 保持不变
app.include_router(ports.router, prefix="/v1/ports", tags=["ports"])
app.include_router(hs.router,    prefix="/v1/hs",    tags=["trade"])
# 统一这里：/v1 + meta 里的 /sources  => /v1/sources
app.include_router(meta.router,  prefix="/v1",       tags=["meta"])  # ← 关键
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)