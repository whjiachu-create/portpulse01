# app/main.py
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import asyncpg
from fastapi import FastAPI, Depends, HTTPException, Query, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi import Security

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="PortPulse & TradeMomentum API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# API Key auth (header: x-api-key). Health & meta 不需要鉴权，其他需要。
# -----------------------------------------------------------------------------
API_KEY_HEADER_NAME = "x-api-key"
_api_key_scheme = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

def _load_api_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}

KNOWN_API_KEYS: set[str] = _load_api_keys()

async def require_api_key(api_key: Optional[str] = Security(_api_key_scheme)) -> str:
    # If no API key configured, allow all (useful for dev)
    if not KNOWN_API_KEYS:
        return ""
    if api_key and api_key in KNOWN_API_KEYS:
        return api_key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

# -----------------------------------------------------------------------------
# Database pool
# -----------------------------------------------------------------------------
DB_DSN = os.getenv("DATABASE_URL")  # e.g. postgresql://.../postgres?sslmode=require

@app.on_event("startup")
async def on_startup() -> None:
    """
    Create a global asyncpg pool if DATABASE_URL is provided.
    Keep app start resilient even when DB is unreachable (health will reflect).
    """
    app.state.pool: Optional[asyncpg.pool.Pool] = None
    app.state.db_error: Optional[str] = None

    if not DB_DSN:
        app.state.db_error = "DATABASE_URL is not set"
        return

    try:
        app.state.pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
    except Exception as e:
        app.state.db_error = f"{type(e).__name__}: {e}"

@app.on_event("shutdown")
async def on_shutdown() -> None:
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if pool:
        await pool.close()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def month_range(frm: datetime, to: datetime) -> List[datetime]:
    cur = datetime(frm.year, frm.month, 1, tzinfo=timezone.utc)
    end = datetime(to.year, to.month, 1, tzinfo=timezone.utc)
    out: List[datetime] = []
    while cur <= end:
        out.append(cur)
        # add ~1 month
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            cur = datetime(cur.year, cur.month + 1, 1, tzinfo=timezone.utc)
    return out

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.get("/v1/health")
async def health() -> Dict[str, Any]:
    """
    Basic liveness + DB connectivity check.
    IMPORTANT: keep SQL in ENGLISH to avoid translation issues.
    """
    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)
    if not pool:
        return {"ok": False, "ts": utc_now_iso(), "db": getattr(app.state, "db_error", "not-initialized")}

    try:
        async with pool.acquire() as conn:
            # DO NOT translate 'SELECT' to any other language.
            await conn.fetchval("SELECT 1;")
        return {"ok": True, "ts": utc_now_iso()}
    except Exception as e:
        return {"ok": False, "ts": utc_now_iso(), "db": f"{type(e).__name__}: {e}"}


@app.get("/v1/meta/sources")
async def meta_sources() -> Dict[str, Any]:
    """
    Static metadata used by the UI/docs.
    """
    return {
        "ports": [
            {"unlocode": "USLAX", "last_updated": "2025-08-12T14:00:00+00:00"},
        ],
        "trade": [
            {"hs": "4202", "last_period": "2024-12-01"},
            {"hs": "9401", "last_period": "2024-12-01"},
        ],
        "version": "1.1",
    }


@app.get("/v1/ports/{unlocode}/snapshot", dependencies=[Depends(require_api_key)])
async def port_snapshot(
    unlocode: str = Path(..., min_length=5, max_length=5, description="UN/LOCODE, e.g. USLAX")
) -> Dict[str, Any]:
    """
    Demo snapshot (lightweight, no DB).
    """
    random.seed(unlocode.upper())
    # Fake numbers deterministically from unlocode
    dwell_gp_share = round(random.uniform(-0.35, 0.15), 4)
    gate_fill = round(random.uniform(0.65, 0.92), 4)
    congestion = round(random.uniform(35, 75), 1)
    return {
        "unlocode": unlocode.upper(),
        "dwell_gp_share": dwell_gp_share,
        "gate_appointment_fill_rate": gate_fill,
        "estimated": True,
        "src": "public_source",
        "src_loaded_at": utc_now_iso(),
        "congestion_score": congestion,
    }


@app.get("/v1/ports/{unlocode}/dwell", dependencies=[Depends(require_api_key)])
async def port_dwell(
    unlocode: str = Path(..., min_length=5, max_length=5, description="UN/LOCODE, e.g. USLAX"),
    months: int = Query(6, ge=1, le=24, description="How many recent months to return"),
) -> List[Dict[str, Any]]:
    """
    Demo dwell history (no DB). Returns last N months with synthetic values.
    """
    base = datetime.now(timezone.utc).replace(day=1)
    series: List[Dict[str, Any]] = []
    random.seed(unlocode.upper() + "DWELL")
    for i in range(months, 0, -1):
        d = (base - timedelta(days=30 * i)).replace(day=1)
        series.append({
            "period": d.date().isoformat(),
            "avg_dwell_days": round(random.uniform(2.0, 6.0), 2),
        })
    return series


@app.get("/v1/hs/{code}/imports", dependencies=[Depends(require_api_key)])
async def hs_imports(
    code: str = Path(..., min_length=2, max_length=6, description="HS code, e.g. 4202"),
    country: str = Query("US", min_length=2, max_length=2, description="ISO2 country code"),
    frm: str = Query(..., description="Start date YYYY-MM-01"),
    to: str = Query(..., description="End date YYYY-MM-01"),
) -> List[Dict[str, Any]]:
    """
    Try to read monthly imports from DB; if not available, return a synthetic series.
    Expected DB table (example):
        trade_monthly(hs text, country text, period date, value_usd numeric)
    """
    # Parse dates (1st of month assumed)
    try:
        frm_dt = datetime.fromisoformat(frm).replace(tzinfo=timezone.utc)
        to_dt = datetime.fromisoformat(to).replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid frm/to; expected 'YYYY-MM-01'")

    pool: Optional[asyncpg.pool.Pool] = getattr(app.state, "pool", None)

    if pool:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT period::date, value_usd
                    FROM trade_monthly
                    WHERE hs = $1 AND country = $2
                      AND period >= $3 AND period <= $4
                    ORDER BY period;
                    """,
                    code, country.upper(), frm_dt.date(), to_dt.date()
                )
                if rows:
                    return [{"period": r["period"].isoformat(), "value_usd": float(r["value_usd"])} for r in rows]
        except Exception:
            # fall back to synthetic if table/columns not present
            pass

    # Synthetic fallback series (deterministic)
    series: List[Dict[str, Any]] = []
    random.seed(f"{code}:{country}")
    for d in month_range(frm_dt, to_dt):
        base = 1_200_000_00  # 1200 * 10^5 just to vary magnitude
        jitter = random.randint(-50_000_00, 50_000_00)
        series.append({"period": d.date().isoformat(), "value_usd": base + jitter})
    return series


# -----------------------------------------------------------------------------
# Local dev entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Local run: uvicorn app.main:app --reload
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )