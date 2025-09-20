from fastapi import APIRouter, Request, Response
from datetime import datetime, timezone
from hashlib import sha256
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

def _make_meta_payload(now_buck: datetime):
    # NOTE:
    # 1) updated_at 使用 5min 桶，避免每秒变化导致 ETag 抖动
    # 2) build 版本&commit 仍从环境读取
    return {
        "sources": [
            {"name": "demo", "type": "synthetic", "freshness": "PT30M", "last_updated": "2025-09-17T00:00:00Z"}
        ],
        "etl": {"window": "hourly", "retries": 2, "backfill": "30d"},
        "build": {
            "version": os.getenv("PORTPULSE_VERSION", "0.1.1"),
            "commit": os.getenv("PORTPULSE_COMMIT")
        },
        "updated_at": now_buck.isoformat()
    }

def _json_body_and_headers(payload: dict) -> tuple[bytes, dict]:
    # 使用稳定序列化（排序键、紧凑分隔符）保证相同内容 → 相同 ETag
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = '"' + sha256(body).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, no-transform",
        "Content-Type": "application/json; charset=utf-8",
        "Vary": "Accept-Encoding",
    }
    return body, headers

def _maybe_304(request: Request, headers: dict) -> Response | None:
    inm = request.headers.get("if-none-match")
    if not inm:
        return None
    candidates = [s.strip() for s in inm.split(",")]
    if headers["ETag"] in candidates or f'W/{headers["ETag"]}' in candidates:
        return Response(status_code=304, headers=headers)
    return None

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
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(content=body, headers=headers)

@router.head("/meta/sources", summary="HEAD for /meta/sources")
def head_meta_sources(request: Request):
    now_buck = _bucket_now_utc(5)
    payload = _make_meta_payload(now_buck)
    _body, headers = _json_body_and_headers(payload)
    maybe = _maybe_304(request, headers)
    if maybe:
        return maybe
    return Response(status_code=200, headers=headers)

# 兼容别名：/v1/sources
@router.get("/sources", summary="(alias) Data sources & ETL metadata")
def sources_alias(request: Request):
    return meta_sources(request)

@router.head("/sources", summary="(alias) HEAD for /sources")
def head_sources_alias(request: Request):
    return head_meta_sources(request)
