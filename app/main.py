# app/main.py
from __future__ import annotations
import logging
import os
from typing import Any, Dict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware import Middleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
from fastapi import HTTPException

from .middlewares import RequestIdMiddleware, AccessLogMiddleware, request_id_var

# -------- 日志基础设置（stdout，INFO） --------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(message)s",  # 我们输出 JSON，避免前缀
)

# -------- 应用 & 中间件 --------
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    description="PortPulse & TradeMomentum API",
    version="1.1",
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -------- 统一错误体工具 --------
def _err_body(request: Request, code: str, message: str, status: int, *, hint: str | None = None, details: Any = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or request_id_var.get()
    body: Dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": rid,
    }
    if hint:
        body["hint"] = hint
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content=body)

# —— 覆盖 FastAPI 默认异常为统一结构 —— #
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # 统一为 {code,message,request_id,details?}
    code = f"http_error_{exc.status_code}"
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return _err_body(request, code, msg, exc.status_code, details=None if isinstance(exc.detail, str) else exc.detail)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return _err_body(request, "validation_error", "Request validation failed", HTTP_422_UNPROCESSABLE_ENTITY, details=exc.errors())

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("portpulse.app").exception("uncaught error: %r", exc)
    return _err_body(request, "internal_error", "Internal server error", HTTP_500_INTERNAL_SERVER_ERROR)

# -------- 根路径跳转到 /docs（保持原有行为） --------
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)

# -------- 健康检查（保留你现有的字段） --------
@app.get("/v1/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    # 如果你在启动阶段把数据库错误放到 app.state.db_error，这里按现状返回
    db_err = getattr(app.state, "db_error", None)
    return {
        "ok": db_err is None,
        "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "db": None if db_err is None else str(db_err),
    }

# -------- 路由装载（按文件存在与否自动装） --------
def _include_router_if_exists(module_path: str, router_name: str, prefix: str, tags: list[str]):
    try:
        mod = __import__(module_path, fromlist=[router_name])
        router = getattr(mod, router_name)
        app.include_router(router, prefix=prefix, tags=tags)
    except Exception as e:
        logging.getLogger("portpulse.app").info("router skipped: %s (%s)", module_path, e)

_include_router_if_exists("app.routers.meta", "router", "/v1/meta", ["meta"])
_include_router_if_exists("app.routers.ports", "router", "/v1/ports", ["ports"])
_include_router_if_exists("app.routers.ports_extra", "router", "/v1/ports", ["ports"])
_include_router_if_exists("app.routers.hs", "router", "/v1", ["trade"])

# -------- 本地调试入口 --------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)