# app/routers/admin_backfill.py
from __future__ import annotations
import os, hmac, logging, asyncio
from datetime import date, timedelta
from typing import List, Dict, Optional

from fastapi import (
    APIRouter, HTTPException, Request, Depends, Query
)
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)
router = APIRouter()

# --- 基础配置 ---------------------------------------------------------------

_DEFAULT_CORE30 = [
    "USLAX","USLGB","USNYC","USSAV","USCHS","USORF","USHOU","USSEA","USOAK","USMIA",
    "NLRTM","BEANR","DEHAM","DEBRV","FRLEH","GBFXT","GBLGP","ESVLC","ESALG","GRPIR",
    "CNSHA","CNNGB","CNSZX","CNTAO","KRPUS","SGSIN","MYTPP","THLCH","INNSA","INMUN",
]

def _core30() -> List[str]:
    env = os.getenv("CORE30_PORTS", "")
    if env.strip():
        return [x.strip().upper() for x in env.split(",") if x.strip()]
    return _DEFAULT_CORE30

def _max_days() -> int:
    """允许的最大天数跨度（含首尾）。默认 7，可通过 BACKFILL_MAX_DAYS=30 放宽。"""
    try:
        v = int(os.getenv("BACKFILL_MAX_DAYS", "7"))
        return max(1, v)
    except Exception:
        return 7

def _secrets_from_env() -> set[str]:
    s = set()
    bf = os.getenv("BACKFILL_SECRET", "")
    adm = os.getenv("ADMIN_SECRET", "")
    if bf:  s.add(bf)
    if adm: s.add(adm)
    return s

def _verify_secret(req: Request) -> bool:
    """
    从 Header/Query 里拿密钥并校验：
    - Headers: X-Admin-Secret 或 X-Backfill-Secret
    - Query:   ?secret= 或 ?token=
    同时支持 BACKFILL_SECRET / ADMIN_SECRET。
    """
    secrets = _secrets_from_env()
    if not secrets:
        raise HTTPException(status_code=503, detail="BACKFILL disabled (no secret set)")

    provided = (
        req.headers.get("X-Admin-Secret")
        or req.headers.get("X-Backfill-Secret")
        or req.query_params.get("secret")
        or req.query_params.get("token")
        or ""
    )

    ok = any(hmac.compare_digest(provided, s) for s in secrets)
    if not ok:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# --- 数据模型 ---------------------------------------------------------------

class BackfillReq(BaseModel):
    ports: List[str]
    start: date
    end: date
    dry_run: bool = True

    @field_validator("ports")
    @classmethod
    def _norm_ports(cls, v: List[str]):
        allow = set(_core30())
        vs = [p.strip().upper() for p in v]
        illegal = [p for p in vs if p not in allow]
        if illegal:
            raise ValueError(f"port(s) not allowed: {illegal}")
        return vs

    @field_validator("end")
    @classmethod
    def _limit_range(cls, v: date, info):
        start = info.data.get("start")
        if start and v < start:
            raise ValueError("end must be >= start")
        if start and (v - start).days + 1 > _max_days():
            raise ValueError(f"max {_max_days()} days range (inclusive)")
        return v

# --- 业务占位（接入你们真实补采） --------------------------------------------

async def _backfill_one(port: str, day: date) -> Dict:
    """
    TODO: 在这里串真实补采逻辑（调用内部 ingest / 触发队列 / 刷新任务等）。
    先放一个占位实现：仅打印日志并返回 queued=True。
    """
    await asyncio.sleep(0)
    logger.info("Backfill queued: port=%s day=%s", port, day.isoformat())
    return {"port": port, "date": day.isoformat(), "queued": True}

def _build_plan(ports: List[str], start: date, end: date) -> List[Dict]:
    plan: List[Dict] = []
    d = start
    while d <= end:
        for p in ports:
            plan.append({"port": p, "date": d.isoformat()})
        d += timedelta(days=1)
    return plan

# --- 路由（两种形态：JSON 与 Path 兼容） -------------------------------------

@router.post("/backfill", summary="Batch backfill (JSON body)")
async def backfill_json(req: BackfillReq, _: bool = Depends(_verify_secret)):
    """
    JSON 形式：
    {
      "ports": ["USLAX","SGSIN"],
      "start": "2025-08-15",
      "end":   "2025-08-21",
      "dry_run": true
    }
    - 端侧只需把 dry_run=false 即可真实入队
    - 最大跨度由 BACKFILL_MAX_DAYS 控制（默认 7）
    """
    plan = _build_plan(req.ports, req.start, req.end)

    if req.dry_run:
        return {"accepted": False, "dry_run": True, "count": len(plan), "plan": plan}

    async def _enqueue_all():
        await asyncio.gather(*[
            _backfill_one(it["port"], date.fromisoformat(it["date"])) for it in plan
        ])

    asyncio.create_task(_enqueue_all())
    return {"accepted": True, "count": len(plan)}

@router.post("/backfill/{unlocode}", summary="Backfill (path style, compatible)")
async def backfill_path_style(
    unlocode: str,
    _: bool = Depends(_verify_secret),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None, alias="to"),
    dry_run: bool = Query(default=False),
):
    """
    兼容你之前的脚本调用：
    POST /v1/admin/backfill/USLAX?secret=...&from=YYYY-MM-DD&to=YYYY-MM-DD&dry_run=0
    - 无需 JSON body
    - 同样受 BACKFILL_MAX_DAYS 限制（默认 7）
    """
    try:
        if not from_ or not to:
            raise ValueError("missing from/to")
        start = date.fromisoformat(from_)
        end = date.fromisoformat(to)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid from/to (YYYY-MM-DD)")

    # 范围校验（含首尾）
    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")
    if (end - start).days + 1 > _max_days():
        raise HTTPException(status_code=422, detail=f"max {_max_days()} days range (inclusive)")

    # 端口校验按 Core30（保持与 JSON 入口一致）
    ports = [unlocode.strip().upper()]
    if ports[0] not in set(_core30()):
        raise HTTPException(status_code=400, detail=f"port not allowed: {ports[0]}")

    plan = _build_plan(ports, start, end)

    if dry_run:
        return {"accepted": False, "dry_run": True, "count": len(plan), "plan": plan}

    async def _enqueue_all():
        await asyncio.gather(*[
            _backfill_one(it["port"], date.fromisoformat(it["date"])) for it in plan
        ])

    asyncio.create_task(_enqueue_all())
    return {"accepted": True, "count": len(plan)}