from __future__ import annotations
import os, json
from datetime import datetime, timezone
from dateutil import tz
from fastapi import APIRouter, Request, HTTPException
import stripe
from app.services.key_utils import generate_key, store_key

router = APIRouter(tags=["webhook"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid signature: {e}")

    # 处理几种关键事件
    if event["type"] in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
        obj = event["data"]["object"]
        # 统一取订阅信息
        if event["type"] == "checkout.session.completed":
            sub_id = obj.get("subscription")
            if sub_id:
                sub = stripe.Subscription.retrieve(sub_id, expand=["plan.product"])
            else:
                sub = None
            customer_id = obj.get("customer")
            price_id = (sub["plan"]["id"] if sub else None)
            current_period_end = (sub["current_period_end"] if sub else None)
        else:
            sub = obj
            customer_id = sub.get("customer")
            price_id = sub["plan"]["id"] if sub and sub.get("plan") else None
            current_period_end = sub.get("current_period_end")

        expires = None
        if current_period_end:
            expires = datetime.fromtimestamp(int(current_period_end), tz=timezone.utc)

        # 业务决定：每次成功都“确保有一把 active key”（如果没有就发一把，有就续期）
        # 简化：直接发新 key（便于初期支持多把并行），后续可按客户策略去重
        plan = "starter"  # 可根据 price_id 映射
        api_key_plain = generate_key("pp_live_")
        await store_key(
            key_plain=api_key_plain,
            owner_email=None,
            plan=plan,
            expires_at=expires,
            stripe_customer_id=customer_id,
            stripe_subscription_id=sub["id"] if sub else None,
            price_id=price_id,
            last4=None,
        )
        return {"ok": True}

    # 其他事件直接返回
    return {"ok": True}