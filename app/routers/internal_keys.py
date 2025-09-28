from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.services.key_utils import (
    extend_key_by_hash,
    generate_key,
    hash_key,
    revoke_key_by_hash,
    store_key,
)

router = APIRouter(prefix="/internal/keys", tags=["internal:keys"])

# ---- 配置 ----
ADMIN_SECRET: str = (os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET") or "").strip()
DEBUG_AUTH: bool = os.getenv("DEBUG_AUTH", "0").strip().lower() in ("1", "true", "yes", "on")


# ---- 工具函数 ----
def _extract_admin_secret(
    *,
    request: Request,
    x_admin_key: Optional[str],
    x_admin_secret: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    """从多处提取 admin secret；优先级：X-Admin-Key > X-Admin-Secret > Authorization: Bearer ..."""
    if x_admin_key:
        return x_admin_key.strip()
    if x_admin_secret:
        return x_admin_secret.strip()
    if authorization:
        s = authorization
        if isinstance(s, (bytes, bytearray)):
            s = s.decode("utf-8", "ignore")
        s = str(s).strip()
        if s.lower().startswith("bearer "):
            return s[7:].strip()
    return None


def _require_admin(secret: Optional[str]) -> None:
    if not ADMIN_SECRET:
        # 与线上 401 语义保持一致
        raise HTTPException(status_code=401, detail="admin secret not configured")
    if not secret or secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---- 调试探针（受 DEBUG_AUTH 保护）----
@router.get("/_fingerprints")
async def _fingerprints():
    if not DEBUG_AUTH:
        raise HTTPException(status_code=404, detail="Not Found")
    h = _sha256_hex(ADMIN_SECRET) if ADMIN_SECRET else None
    return {
        "configured": bool(ADMIN_SECRET),
        "len": len(ADMIN_SECRET or ""),
        "sha256_prefix": (h[:12] if h else None),
    }


@router.get("/_inspect_headers")
async def _inspect_headers(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if not DEBUG_AUTH:
        raise HTTPException(status_code=404, detail="Not Found")
    provided = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    h = _sha256_hex(provided) if provided else None
    source = (
        "X-Admin-Key"
        if x_admin_key
        else ("X-Admin-Secret" if x_admin_secret else ("Authorization: Bearer" if (authorization and str(authorization).lower().startswith("bearer ")) else None))
    )
    return {"source": source, "len": len(provided or ""), "sha256_prefix": (h[:12] if h else None)}


# ---- 自检 ----
@router.get("/ping")
async def ping(
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    secret = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    _require_admin(secret)
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


# ---- 模型 ----
class IssueReq(BaseModel):
    owner_email: Optional[EmailStr] = None
    plan: str = Field(default="starter", pattern=r"^(lite|starter|pro|enterprise)$|^starter$")
    months: int = Field(default=1, ge=1, le=36)
    prefix: str = Field(default="pp_live_", pattern=r"^(pp_live_|pp_dev_|pp_demo_)$")


class IssueResp(BaseModel):
    api_key: str
    expires_at: datetime


class RevokeReq(BaseModel):
    api_key: str


class ExtendReq(BaseModel):
    api_key: str
    months: int = Field(ge=1, le=36)


# ---- 发放 ----
@router.post("/issue", response_model=IssueResp)
async def issue_key(
    body: IssueReq,
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    secret = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    _require_admin(secret)

    plain = generate_key(prefix=body.prefix)
    expires = datetime.now(timezone.utc) + timedelta(days=30 * body.months)

    await store_key(
        key_plain=plain,
        owner_email=body.owner_email,
        plan=body.plan,
        expires_at=expires,
    )
    return IssueResp(api_key=plain, expires_at=expires)


# ---- 吊销 ----
@router.post("/revoke")
async def revoke_key(
    body: RevokeReq,
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    secret = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    _require_admin(secret)

    cnt = await revoke_key_by_hash(hash_key(body.api_key))
    return {"revoked": int(cnt)}


# ---- 延期 ----
@router.post("/extend")
async def extend_key(
    body: ExtendReq,
    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    secret = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    _require_admin(secret)

    cnt = await extend_key_by_hash(hash_key(body.api_key), days=30 * body.months)
    return {"extended": int(cnt)}
