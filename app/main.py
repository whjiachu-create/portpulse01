# app/main.py
import os
import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any

import asyncpg
from fastapi import FastAPI, Depends, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    # 本地开发时从 .env 读取
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

log = logging.getLogger("uvicorn")

APP_TITLE = "PortPulse & TradeMomentum API"
APP_VERSION = "1.1"

# 环境变量
DB_DSN = os.getenv("DATABASE_URL", "").strip()
# 支持多个 key，用逗号分隔： e.g. "dev_key_123, another_key"
API_KEYS_RAW = os.getenv("API_KEYS", "").strip()
API_KEYS: List[str] = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]

# FastAPI
app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# CORS（如需限制可按需修改）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局连接池（可能为 None）
POOL: Optional[asyncpg.Pool] = None


# -------------------------
# 启停钩子：尽量建池，但失败不崩
# -------------------------
@app.on_event("startup")
async def startup() -> None:
    global POOL
    if not DB_DSN:
        log.warning("DATABASE_URL 未设置，跳过创建数据库连接池")
        POOL = None
        return

    # Railway/Supabase 上建议使用 6543（pgBouncer）+ sslmode=require
    # DSN 中已携带 sslmode=require 时，asyncpg 会启用 TLS
    try:
        POOL = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=5,
            timeout=10,           # 建连超时
            command_timeout=30,   # SQL 命令超时
        )
        log.info("DB pool created")
    except Exception as e:
        # 不能连库时不要让进程退出；相关接口返回 503
        log.error("创建 DB 连接池失败：%r（服务仍会启动）", e)
        POOL = None


@app.on_event("shutdown")
async def shutdown() -> None:
    global POOL
    if POOL is not None:
        try:
            await POOL.close()
        except Exception:
            pass
        POOL = None


def require_db_pool() -> asyncpg.Pool:
    """只有在真正需要访问数据库的接口里调用。"""
    if POOL is None:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    return POOL


# -------------------------
# 简单 API Key 鉴权
# -------------------------
def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    # 若未配置 API_KEYS，则视为无需鉴权
    if not API_KEYS:
        return
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Unauthorized")


# -------------------------
# 公共端点（无需鉴权）
# -------------------------
from datetime import datetime, timezone

@app.get("/v1/health")
async def health():
    # 简单连库探活
    async with app.state.pool.acquire() as conn:
        await conn.fetchval("SELECT 1;")   # 注意：必须是 SELECT，不要被翻译成“选择”
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/meta/sources")
async def meta_sources() -> Dict[str, Any]:
    """
    返回数据源的最近更新时间/期间。
    - 端口拥堵：来自物化视图/汇总表 agg_port_congestion（按 port_unlocode 聚合）
    - 贸易月度：来自 fact_trade_monthly（按 hs_code 聚合）
    """
    pool = require_db_pool()
    ports: List[Dict[str, Any]] = []
    trade: List[Dict[str, Any]] = []

    async with pool.acquire() as conn:
        # 端口：各港口最新 ts_bucket
        try:
            rows = await conn.fetch(
                """
                SELECT port_unlocode, MAX(ts_bucket) AS last_updated
                FROM agg_port_congestion
                GROUP BY 1
                ORDER BY 1
                """
            )
            ports = [
                {
                    "unlocode": r["port_unlocode"],
                    "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
                }
                for r in rows
            ]
        except Exception as e:
            log.error("查询端口元数据失败：%r", e)

        # 贸易：各 HS 的最新期间
        try:
            rows = await conn.fetch(
                """
                SELECT hs_code, MAX(period) AS last_period
                FROM fact_trade_monthly
                GROUP BY 1
                ORDER BY 1
                """
            )
            trade = [
                {
                    "hs": r["hs_code"],
                    "last_period": r["last_period"].isoformat() if isinstance(r["last_period"], (datetime, date)) else str(r["last_period"]),
                }
                for r in rows
            ]
        except Exception as e:
            log.error("查询贸易元数据失败：%r", e)

    return {
        "ports": ports,
        "trade": trade,
        "version": APP_VERSION,
    }


# -------------------------
# 端口相关（需要 API Key）
# -------------------------
@app.get("/v1/ports/{unlocode}/snapshot", dependencies=[Depends(require_api_key)])
async def port_snapshot(unlocode: str) -> Dict[str, Any]:
    """
    返回给定港口最近一个时间桶的拥堵快照。
    依赖表/视图：agg_port_congestion(port_unlocode, ts_bucket, congestion_score, ...)
    """
    pool = require_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT port_unlocode, ts_bucket, congestion_score
            FROM agg_port_congestion
            WHERE port_unlocode = $1
            ORDER BY ts_bucket DESC
            LIMIT 1
            """,
            unlocode.upper(),
        )
        if not row:
            raise HTTPException(status_code=404, detail="port not found")

        return {
            "port_unlocode": row["port_unlocode"],
            "ts_bucket": row["ts_bucket"].isoformat(),
            "congestion_score": float(row["congestion_score"]) if row["congestion_score"] is not None else None,
            # 补充信息（可按需修改）
            "src": "public_source",
            "src_loaded_at": datetime.now(timezone.utc).isoformat(),
            "estimated": True,
        }


@app.get("/v1/ports/{unlocode}/dwell", dependencies=[Depends(require_api_key)])
async def port_dwell(
    unlocode: str,
    limit: int = Query(48, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """
    返回近若干个时间桶的拥堵时间序列（这里示例返回 ts_bucket + congestion_score）。
    如需更细粒度的 dwell 字段，可在 SQL 中补充选择列。
    """
    pool = require_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ts_bucket, congestion_score
            FROM agg_port_congestion
            WHERE port_unlocode = $1
            ORDER BY ts_bucket DESC
            LIMIT $2
            """,
            unlocode.upper(),
            limit,
        )
    data = [
        {
            "ts_bucket": r["ts_bucket"].isoformat(),
            "congestion_score": float(r["congestion_score"]) if r["congestion_score"] is not None else None,
        }
        for r in rows
    ]
    # 逆序为时间正序
    return list(reversed(data))


# -------------------------
# 贸易相关（需要 API Key）
# -------------------------
@app.get("/v1/hs/{code}/imports", dependencies=[Depends(require_api_key)])
async def hs_imports(
    code: str,
    country: str = Query("US", description="ISO3, e.g. US"),
    frm: Optional[date] = Query(None, alias="frm", description="起始 YYYY-MM-01"),
    to: Optional[date] = Query(None, alias="to", description="结束 YYYY-MM-01（含）"),
) -> List[Dict[str, Any]]:
    """
    返回某 HS（2/4/6位均可存成字符串）在指定国家的月度进口额。
    依赖表：fact_trade_monthly(country_iso3, hs_code, period, value_usd, src, src_loaded_at)
    """
    pool = require_db_pool()
    hs_code = str(code).strip()

    # 若未指定时间范围，默认返回最近 12 期
    where, args = ["country_iso3 = $1", "hs_code = $2"], [country.upper(), hs_code]
    if frm and to:
        where.append("period BETWEEN $3 AND $4")
        args.extend([frm, to])
    elif frm and not to:
        where.append("period >= $3")
        args.append(frm)
    elif to and not frm:
        where.append("period <= $3")
        args.append(to)

    sql = f"""
        SELECT country_iso3, hs_code, period, value_usd, src, src_loaded_at
        FROM fact_trade_monthly
        WHERE {' AND '.join(where)}
        ORDER BY period ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)

    # 如果没给时间范围且结果为空，尝试按 hs_code 最近 12 期
    if not rows and not (frm or to):
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT country_iso3, hs_code, period, value_usd, src, src_loaded_at
                FROM fact_trade_monthly
                WHERE country_iso3 = $1 AND hs_code = $2
                ORDER BY period DESC
                LIMIT 12
                """,
                country.upper(),
                hs_code,
            )
        rows = list(reversed(rows))

    return [
        {
            "country_iso3": r["country_iso3"],
            "hs_code": r["hs_code"],
            "period": r["period"].isoformat() if isinstance(r["period"], (datetime, date)) else str(r["period"]),
            "value_usd": float(r["value_usd"]) if r["value_usd"] is not None else None,
            "src": r.get("src") if "src" in r else None,
            "src_loaded_at": (
                r["src_loaded_at"].isoformat() if "src_loaded_at" in r and r["src_loaded_at"] else None
            ),
        }
        for r in rows
    ]


# -------------------------
# 本地开发启动（Railway/Procfile 用 uvicorn 启动）
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("DEV_RELOAD", "")),
    )