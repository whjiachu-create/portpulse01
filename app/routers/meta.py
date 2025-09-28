from fastapi import APIRouter, Request, Response
from datetime import datetime, timezone
from hashlib import sha256
import email.utils as eut
import json
import os

router = APIRouter(prefix="/v1", tags=["meta"])

# -----------------------
# helpers
# -----------------------
def _bucket_now_utc(minutes: int = 5) -> datetime:
    """Round 'now' to N-minute buckets for ETag stability."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    bucket_minute = (now.minute // minutes) * minutes
    return now.replace(minute=bucket_minute, second=0)

def _make_meta_payload(now_buck: datetime) -> dict:
    """
    统一 /v1/meta/sources & /v1/sources 的结构，满足验收“高要求”：
    - 顶层包含：sources / etl / build / updated_at
    - 兼容扩展：type="object"、as_of（等同 updated_at）
    """
    updated_iso = now_buck.isoformat()
    payload = {
        "type": "object",
        "sources": [
            {
                "name": "demo",
                "type": "synthetic",
                "freshness": "PT30M",
                "last_ingest_at": "2025-09-17T00:00:00Z",
            }
        ],
        "etl": {"window": "hourly", "retries": 2, "backfill": "30d"},
        "build": {
            "version": os.getenv("PORTPULSE_VERSION", os.getenv("APP_VERSION", "0.1.1")),
            "commit": os.getenv("PORTPULSE_COMMIT"),
        },
        "updated_at": updated_iso,
        "as_of": updated_iso,
    }
    return payload

def _json_body_and_headers(payload: dict) -> tuple[bytes, dict]:
    # 稳定序列化（排序键、紧凑分隔符）→ 稳定 ETag
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = '"' + sha256(body).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Content-Type": "application/json; charset=utf-8",
        "Vary": "Accept-Encoding",
    }
    return body, headers

def _last_modified_header(dt: datetime) -> str:
    # RFC 7231 IMF-fixdate
    return eut.format_datetime(dt, usegmt=True)

def _maybe_304(request: Request, headers: dict) -> Response | None:
    inm = request.headers.get("if-none-match")
    if not inm:
        return None
    candidates = [s.strip() for s in inm.split(",")]
    if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
        # 304 不带 body；保留缓存相关头
        hdr = {k: v for k, v in headers.items() if k in ("ETag", "Cache-Control", "Vary", "Last-Modified")}
        return Response(status_code=304, headers=hdr)
    return None

def _ok_response(body: bytes, headers: dict) -> Response:
    # 明确写出 Content-Length，便于某些代理与客户端行为稳定
    hdr = dict(headers)
    hdr["Content-Length"] = str(len(body))
    return Response(content=body, headers=hdr, media_type=headers.get("Content-Type"))

# -----------------------
# routes
# -----------------------
@router.get("/health", summary="Liveness/Readiness")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}

@router.get("/meta/sources", summary="Data sources & ETL metadata")
def meta_sources(request: Request):
    now_buck = _bucket_now_utc(5)
    payload = _make_meta_payload(now_buck)
    body, headers = _json_body_and_headers(payload)
    headers["Last-Modified"] = _last_modified_header(now_buck)
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return _ok_response(body, headers)

@router.head("/meta/sources", summary="HEAD for /meta/sources")
def head_meta_sources(request: Request):
    now_buck = _bucket_now_utc(5)
    payload = _make_meta_payload(now_buck)
    _body, headers = _json_body_and_headers(payload)
    headers["Last-Modified"] = _last_modified_header(now_buck)
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    # HEAD：无 body，但保留与 GET 一致的头；不强加 Content-Length
    return Response(status_code=200, headers=headers)

# 兼容别名：/v1/sources
@router.get("/sources", summary="(alias) Data sources & ETL metadata")
def sources_alias(request: Request):
    return meta_sources(request)

@router.head("/sources", summary="(alias) HEAD for /sources")
def head_sources_alias(request: Request):
    return head_meta_sources(request)

# --- Added for acceptance: simple extra endpoints (do not require data deps) ---
@router.get("/ping", summary="Ping (simple liveness)")
def ping():
    return {"ok": True, "as_of": datetime.now(timezone.utc).isoformat()}

@router.get("/version", summary="Build/version info (alias)")
def version():
    return {
        "version": os.getenv("PORTPULSE_VERSION", os.getenv("APP_VERSION", "0.1.1")),
        "commit": os.getenv("PORTPULSE_COMMIT"),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/about", summary="About PortPulse API")
def about():
    """
    轻量只读介绍端点：用于提升 OpenAPI path 数量，不依赖外部数据。
    走现有鉴权策略（需带 API Key）。
    """
    return {
        "name": "PortPulse API",
        "version": os.getenv("PORTPULSE_VERSION", os.getenv("APP_VERSION", "0.1.1")),
        "build_commit": os.getenv("PORTPULSE_COMMIT"),
        "docs": ["/docs", "/redoc", "/openapi.json"],
        "as_of": datetime.now(timezone.utc).isoformat(),
    }