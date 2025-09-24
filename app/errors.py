from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uuid

ERROR_SHAPE_KEYS = ("code","message","request_id","hint")

def _mk_id(req: Request) -> str:
    rid = (req.headers.get("x-request-id")
           or getattr(getattr(req, "state", None), "request_id", None)
           or str(uuid.uuid4()))
    return rid

def _shape(body: dict, req: Request, default_code="bad_request", hint=None):
    rid = _mk_id(req)
    msg = body.get("message") or body.get("detail") or body.get("msg") or "Bad request"
    code = body.get("code") or default_code
    shaped = {
        "code": str(code),
        "message": str(msg),
        "request_id": rid,
        "hint": hint or body.get("hint") or ""
    }
    return shaped, rid

def http_exception_handler(req: Request, exc: HTTPException):
    raw = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    shaped, rid = _shape(raw, req, default_code = raw.get("code") or (
        "not_found" if exc.status_code == 404 else "http_error"))
    resp = JSONResponse(status_code=exc.status_code, content=shaped)
    resp.headers["x-request-id"] = rid
    return resp

def validation_exception_handler(req: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg") or "Validation error"
    shaped, rid = _shape({"message": msg}, req, default_code="invalid_request")
    resp = JSONResponse(status_code=422, content=shaped)
    resp.headers["x-request-id"] = rid
    return resp

def generic_exception_handler(req: Request, exc: Exception):
    shaped, rid = _shape({"message": "Internal server error"}, req, default_code="internal")
    resp = JSONResponse(status_code=500, content=shaped)
    resp.headers["x-request-id"] = rid
    return resp

def install_error_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # app.add_exception_handler(Exception, generic_exception_handler)
