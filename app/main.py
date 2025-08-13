# app/main.py  —— 启用 Swagger 全局 Authorize（API Key）
import os, asyncpg, datetime as dt
from typing import Optional
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()
DB = os.getenv("DATABASE_URL")
API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "dev_key_123").split(",") if k.strip()]

# 让 Swagger 记住授权（出现 Authorize 按钮）
app = FastAPI(
    title="PortPulse & TradeMomentum API",
    version="1.1",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 连接池
pool: asyncpg.Pool = None
@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(dsn=DB, min_size=1, max_size=5)

# —— 安全方案：X-API-Key 头（给 Swagger 用）——
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(x_api_key: Optional[str] = Security(api_key_header)):
    if x_api_key and x_api_key in API_KEYS:
        return x_api_key
    raise HTTPException(status_code=401, detail="Invalid API key")

# ===== 公开端点（不需要密钥）=====
@app.get("/v1/health")
async def health():
    async with pool.acquire() as conn:
        ok = await conn.fetchval("select 1;")
    return {"ok": ok == 1, "ts": dt.datetime.utcnow().isoformat() + "Z"}

@app.get("/v1/meta/sources")
async def meta_sources():
    q1 = "select port_unlocode, max(ts_bucket) last_ts from fact_port_ops group by 1 order by 1;"
    q2 = "select hs_code, max(period) last_period from fact_trade_monthly group by 1 order by 1;"
    async with pool.acquire() as conn:
        ports = await conn.fetch(q1)
        trade = await conn.fetch(q2)
    return {
        "ports": [{"unlocode": r["port_unlocode"], "last_updated": r["last_ts"]} for r in ports],
        "trade": [{"hs": r["hs_code"], "last_period": r["last_period"]} for r in trade],
        "version": "1.1",
    }

# ===== 需密钥的业务端点（在函数签名里声明依赖 Security）=====
@app.get("/v1/ports/{unlocode}/snapshot")
async def port_snapshot(unlocode: str, api_key: str = Security(get_api_key)):
    sql = """
    with last as (
      select * from fact_port_ops where port_unlocode=$1 order by ts_bucket desc limit 1
    )
    select l.*, a.congestion_score
    from last l left join agg_port_congestion a
      on a.port_unlocode=l.port_unlocode and a.ts_bucket=l.ts_bucket;
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, unlocode.upper())
    if not row:
        raise HTTPException(404, "No data")
    return dict(row)

@app.get("/v1/ports/{unlocode}/dwell")
async def port_dwell(unlocode: str, date: Optional[str] = None, api_key: str = Security(get_api_key)):
    where, params = "", [unlocode.upper()]
    if date:
        try:
            d = dt.date.fromisoformat(date)
        except Exception:
            raise HTTPException(400, "Invalid date")
        where, params = "and date(ts_bucket) = $2", [unlocode.upper(), d]
    sql = f"""
    select date(ts_bucket) as date, dwell_0_4_share, dwell_5_8_share, dwell_9p_share
    from fact_port_ops where port_unlocode=$1 {where}
    order by date desc limit 14;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]

@app.get("/v1/hs/{code}/imports")
async def hs_imports(code: str, country: str = "US",
                     frm: str = "2024-01-01", to: str = "2024-12-01",
                     api_key: str = Security(get_api_key)):
    try:
        d0 = dt.date.fromisoformat(frm); d1 = dt.date.fromisoformat(to)
    except Exception:
        raise HTTPException(400, "Invalid frm/to")
    sql = """
    select period, value_usd
      from fact_trade_monthly
     where country_iso3=$1 and hs_code=$2 and period between $3 and $4
     order by period;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, country.upper(), code, d0, d1)
    return [{"period": r["period"], "value_usd": float(r["value_usd"])} for r in rows]