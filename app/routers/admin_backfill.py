# app/routers/admin_backfill.py
from __future__ import annotations
import os, hmac, logging, asyncio, importlib
from datetime import date, timedelta
from typing import List, Dict, Optional, Set

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

# -------------------- Core30 baseline --------------------
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
    """Inclusive range guard; default 7, overridable via BACKFILL_MAX_DAYS."""
    try:
        v = int(os.getenv("BACKFILL_MAX_DAYS", "7"))
        return max(1, v)
    except Exception:
        return 7

def _secrets_from_env() -> Set[str]:
    s: Set[str] = set()
    for k in ("BACKFILL_SECRET", "ADMIN_SECRET"):
        v = os.getenv(k, "")
        if v:
            s.add(v)
    return s

def _verify_secret(req: Request) -> bool:
    """
    Accept secret from:
      - Headers: X-Admin-Secret / X-Backfill-Secret
      - Query:   ?secret= / ?token=
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
    if not any(hmac.compare_digest(provided, s) for s in secrets):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# -------------------- optional ingest wiring --------------------
def _get_ingest_fn():
    """
    Optional real ETL hook (sync mode):
        app/services/ingesters.py   ->  async def ingest_port_day(port: str, day: date) -> dict
    When absent, sync calls will return a hint and never 500.
    """
    try:
        mod = importlib.import_module("app.services.ingesters")
        fn = getattr(mod, "ingest_port_day", None)
        return fn if callable(fn) else None
    except Exception:
        return None

async def _backfill_one(port: str, day: date, sync: bool) -> Dict:
    if sync:
        ingest = _get_ingest_fn()
        if ingest is None:
            logger.warning("INGEST_FN missing: port=%s day=%s", port, day)
            return {"port": port, "date": day.isoformat(), "queued": False, "synced": False,
                    "hint": "INGEST_FN not wired"}
        try:
            res = await ingest(port, day)
            return {"port": port, "date": day.isoformat(), "queued": False, "synced": True, "result": res}
        except Exception as e:
            logger.exception("ingest_port_day failed: %s", e)
            raise HTTPException(status_code=500, detail=f"ingest failed: {e}")
    else:
        # async enqueue placeholder (no real queue wired yet)
        await asyncio.sleep(0)
        logger.info("Backfill queued (noop): port=%s day=%s", port, day)
        return {"port": port, "date": day.isoformat(), "queued": True}

def _build_plan(ports: List[str], start: date, end: date) -> List[Dict]:
    plan: List[Dict] = []
    d = start
    while d <= end:
        for p in ports:
            plan.append({"port": p, "date": d.isoformat()})
        d += timedelta(days=1)
    return plan

# -------------------- models --------------------
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

# -------------------- routes --------------------
@router.post("/backfill", summary="Batch backfill (JSON body)")
async def backfill_json(
    req: BackfillReq,
    _: bool = Depends(_verify_secret),
    sync: bool = Query(default=False, description="Execute synchronously (for testing)"),
):
    """
    Example:
    POST /v1/admin/backfill?sync=1
    {
      "ports": ["USLAX", "SGSIN"],
      "start": "2025-09-01",
      "end":   "2025-09-07",
      "dry_run": false
    }
    """
    plan = _build_plan(req.ports, req.start, req.end)
    if req.dry_run:
        return {"accepted": False, "dry_run": True, "count": len(plan), "plan_len": len(plan)}

    if sync:
        results = [await _backfill_one(it["port"], date.fromisoformat(it["date"]), True) for it in plan]
        return {"accepted": True, "count": len(results), "synced": True, "results": results}

    async def _enqueue_all():
        await asyncio.gather(*[
            _backfill_one(it["port"], date.fromisoformat(it["date"]), False) for it in plan
        ])
    asyncio.create_task(_enqueue_all())
    return {"accepted": True, "count": len(plan), "synced": False}

@router.post("/backfill/{unlocode}", summary="Backfill (range via from/to)")
async def backfill_path_style(
    unlocode: str,
    _: bool = Depends(_verify_secret),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None, alias="to"),
    sync: bool = Query(default=False),
):
    """
    Example:
    POST /v1/admin/backfill/USLAX?from=2025-09-01&amp;to=2025-09-07&amp;sync=1
    """
    if not from_ or not to:
        raise HTTPException(status_code=422, detail="Invalid from/to (YYYY-MM-DD)")
    try:
        start = date.fromisoformat(from_)
        end = date.fromisoformat(to)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid from/to (YYYY-MM-DD)")

    if end < start:
        raise HTTPException(status_code=422, detail="end must be >= start")
    if (end - start).days + 1 > _max_days():
        raise HTTPException(status_code=422, detail=f"max {_max_days()} days range (inclusive)")

    code = unlocode.strip().upper()
    if code not in set(_core30()):
        raise HTTPException(status_code=400, detail=f"port not allowed: {code}")

    plan = _build_plan([code], start, end)
    if sync:
        results = [await _backfill_one(code, date.fromisoformat(it["date"]), True) for it in plan]
        return {"accepted": True, "count": len(results), "synced": True, "results": results}

    async def _enqueue_all():
        await asyncio.gather(*[
            _backfill_one(code, date.fromisoformat(it["date"]), False) for it in plan
        ])
    asyncio.create_task(_enqueue_all())
    return {"accepted": True, "count": len(plan), "synced": False}

@router.post("/backfill/ports/{unlocode}", summary="Backfill by days (compat for legacy scripts)")
async def backfill_days_style(
    unlocode: str,
    _: bool = Depends(_verify_secret),
    days: int = Query(default=7, ge=1, description="Inclusive, capped by BACKFILL_MAX_DAYS"),
    sync: bool = Query(default=False),
):
    """
    Example:
    POST /v1/admin/backfill/ports/USLAX?days=7&amp;sync=1
    """
    days = min(days, _max_days())
    code = unlocode.strip().upper()
    if code not in set(_core30()):
        raise HTTPException(status_code=400, detail=f"port not allowed: {code}")

    end = date.today()
    start = end - timedelta(days=days - 1)
    plan = _build_plan([code], start, end)

    if sync:
        results = [await _backfill_one(code, date.fromisoformat(it["date"]), True) for it in plan]
        return {
            "accepted": True,
            "count": len(results),
            "synced": True,
            "range": f"{start}..{end}",
            "results": results,
        }

    async def _enqueue_all():
        await asyncio.gather(*[
            _backfill_one(code, date.fromisoformat(it["date"]), False) for it in plan
        ])
    asyncio.create_task(_enqueue_all())
    return {"accepted": True, "count": len(plan), "synced": False, "range": f"{start}..{end}"}