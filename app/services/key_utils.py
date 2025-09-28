from __future__ import annotations
import os, secrets, hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import text
from app.db import engine

PEPPER = os.getenv("API_KEY_PEPPER", "dev_pepper")

def generate_key(prefix: str = "pp_live_") -> str:
    # 32字节随机 → 64hex，带前缀
    return prefix + secrets.token_hex(16)

def hash_key(plain: str) -> str:
    return hashlib.sha256((plain + PEPPER).encode("utf-8")).hexdigest()

async def store_key(
    key_plain: str,
    owner_email: Optional[str],
    plan: str,
    expires_at: Optional[datetime],
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    price_id: Optional[str] = None,
    last4: Optional[str] = None,
    prefix: Optional[str] = None,
) -> Tuple[str, str]:
    """写入 api_keys（只存 hash），返回 (key_plain, key_hash)"""
    key_hash = hash_key(key_plain)
    if prefix is None:
        prefix = "pp_live_" if key_plain.startswith("pp_live_") else "pp_dev_"
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO api_keys
              (key_hash,prefix,owner_email,plan,expires_at,
               stripe_customer_id,stripe_subscription_id,price_id,last4,status,updated_at)
            VALUES
              (:key_hash,:prefix,:owner_email,:plan,:expires_at,
               :cus,:sub,:price,:last4,'active',CURRENT_TIMESTAMP)
            ON CONFLICT(key_hash) DO UPDATE SET
              owner_email=excluded.owner_email,
              plan=excluded.plan,
              expires_at=excluded.expires_at,
              stripe_customer_id=excluded.stripe_customer_id,
              stripe_subscription_id=excluded.stripe_subscription_id,
              price_id=excluded.price_id,
              last4=excluded.last4,
              status='active',
              updated_at=CURRENT_TIMESTAMP
        """), dict(
            key_hash=key_hash, prefix=prefix, owner_email=owner_email or None, plan=plan,
            expires_at=expires_at, cus=stripe_customer_id, sub=stripe_subscription_id,
            price=price_id, last4=last4
        ))
    return key_plain, key_hash

async def revoke_key_by_hash(key_hash: str) -> int:
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            UPDATE api_keys SET status='revoked', updated_at=CURRENT_TIMESTAMP
            WHERE key_hash=:h AND status!='revoked'
        """), dict(h=key_hash))
        return r.rowcount

async def extend_key_by_hash(key_hash: str, days: int) -> int:
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            UPDATE api_keys
            SET expires_at=COALESCE(expires_at, CURRENT_TIMESTAMP) + :days, updated_at=CURRENT_TIMESTAMP
            WHERE key_hash=:h AND status='active'
        """), dict(h=key_hash, days=f"{days} days"))
        return r.rowcount

async def expire_due_keys(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            UPDATE api_keys
            SET status='expired', updated_at=CURRENT_TIMESTAMP
            WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= :now
        """), dict(now=now))
        return r.rowcount