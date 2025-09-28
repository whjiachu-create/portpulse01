from __future__ import annotations

import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr

from app.services.key_utils import (
    generate_key,
    store_key,
    hash_key,
    revoke_key_by_hash,
    extend_key_by_hash,
)

router = APIRouter(prefix="/internal/keys", tags=["internal:keys"])\n\nDEBUG_AUTH = (os.getenv("DEBUG_AUTH","0").strip() in ("1","true","yes","on"))


# -----------------------
# helpers
# -----------------------
def _normalize_secret(s: Optional[str]) -> str:
    """
    标准化密钥：
    - 去掉首尾空白
    - 去掉成对包裹的引号（'xxx' / "xxx"）
    - 返回字符串（即使传入 None）
    """
    if s is None:
        return ""
    v = str(s).strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1].strip()
    return v


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# 读取并规整环境变量（去空白/去引号）
ADMIN_SECRET = _normalize_secret(os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET"))


def _extract_admin_secret(
    *,
    request: Request,
    x_admin_key: Optional[str],
    x_admin_secret: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    """
    从多个常见位置提取管理员密钥；全部标准化。
    优先级：X-Admin-Key > X-Admin-Secret > Authorization: Bearer xxx
    """
    if x_admin_key:
        return _normalize_secret(x_admin_key)
    if x_admin_secret:
        return _normalize_secret(x_admin_secret)
    if authorization:
        auth = authorization
        if isinstance(auth, (bytes, bytearray)):
            auth = auth.decode("utf-8", "ignore")
        s = str(auth).strip()
        if s.lower().startswith("bearer "):
            return _normalize_secret(s[7:])
    return None


def _auth(admin_secret: Optional[str]):
    # 明确区分“未配置密钥”和“密钥不匹配”
    if not ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="admin secret not configured")
    if not admin_secret or _normalize_secret(admin_secret) != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")


# -----------------------
# 调试端点（本地排查用；上线前建议删除）
# -----------------------
@router.get("/_debug")
async def _check_gate():
    if not DEBUG_AUTH:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    return await debug_admin_secret_len()

@router.get("/_debug")
async def debug_admin_secret_len_gate():
    if not DEBUG_AUTH:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    return debug_admin_secret_len_impl()

async def debug_admin_secret_len_impl():
    """不泄露密钥，只返回长度与是否设置；用于快速判断进程是否读取到了 ADMIN_API_KEY。"""
    return {
        "configured": bool(ADMIN_SECRET),
        "length": len(ADMIN_SECRET),
    }


@router.get("/_fingerprints")
async def fingerprints_gate():
    if not DEBUG_AUTH:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    return fingerprints_impl()

async def fingerprints_impl():
    """返回服务端 ADMIN_API_KEY 的长度与 sha256 指纹（前 12 位）"""
    h = _sha256_hex(ADMIN_SECRET) if ADMIN_SECRET else None
    return {
        "configured": bool(ADMIN_SECRET),
        "len": len(ADMIN_SECRET),
        "sha256_prefix": (h[:12] if h else None),
    }


@router.get("/_inspect_headers")
async def inspect_headers_gate(
    request: Request,
    x_admin_key: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    if not DEBUG_AUTH:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    return inspect_headers_impl(

    request: Request,
    x_admin_key: Optional[str] = Header(default=None),
    x_admin_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """抽取本次请求携带的 admin secret，并返回来源、长度与 sha256 指纹（前 12 位）"""
    provided = _extract_admin_secret(
        request=request,
        x_admin_key=x_admin_key,
        x_admin_secret=x_admin_secret,
        authorization=authorization,
    )
    h = _sha256_hex(provided) if provided else None
    source = (
        "X-Admin-Key" if x_admin_key else
        "X-Admin-Secret" if x_admin_secret else
        ("Authorization: Bearer" if (authorization and str(authorization).lower().startswith("bearer ")) else None)
    )
    return {
        "source": source,
        "len": len(provided or ""),
        "sha256_prefix": (h[:12] if h else None),
    }


# -----------------------
# Pydantic models
# -----------------------
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


# -----------------------
# routes
# -----------------------
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
    _auth(secret)
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


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
    _auth(secret)

    plain = generate_key(prefix=body.prefix)
    # 月份转天：按 30 天/月简单估算
    expires = datetime.now(timezone.utc) + timedelta(days=30 * body.months)

    await store_key(
        key_plain=plain,
        owner_email=body.owner_email,
        plan=body.plan,
        expires_at=expires,
    )
    return IssueResp(api_key=plain, expires_at=expires)


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
    _auth(secret)

    cnt = await revoke_key_by_hash(hash_key(body.api_key))
    return {"revoked": int(cnt)}


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
    _auth(secret)

    cnt = await extend_key_by_hash(hash_key(body.api_key), days=30 * body.months)
    return {"extended": int(cnt)}