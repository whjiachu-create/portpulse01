# app/routers/meta.py
from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Response
import json

from app.dependencies import get_db_pool
from app.models import Source
from datetime import datetime, timezone

router = APIRouter(tags=["meta"])

@router.get("/sources", response_model=list[Source])
async def list_sources(response: Response, pool = Depends(get_db_pool)):
    rows = await pool.fetch(
        "SELECT id, name, url, last_updated FROM public.sources ORDER BY id;"
    )
    sources = [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "url": r["url"],
            "last_updated": r["last_updated"].isoformat(),
        }
        for r in rows
    ]
    # 修改 Cache-Control 头，统一为 public, max-age=300, s-maxage=300
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return sources

# 健康检查（DB 可选）
@router.get("/health", tags=["meta"])
async def health(response: Response):
    # 统一返回：ok/ts/db（db 异常时返回错误摘要字符串）
    now_iso = datetime.now(timezone.utc).isoformat()
    pool = getattr(app.state, "pool", None) if hasattr(app, 'state') else None

    # 获取应用版本（从环境变量或默认值）
    version = os.getenv("APP_VERSION", "unknown")

    # 获取部署区域（从环境变量或默认值）
    region = os.getenv("RAILWAY_REGION", os.getenv("REGION", "unknown"))

    # 计算运行时间（秒）
    uptime_seconds = time.time() - getattr(app.state, "start_time", time.time()) if hasattr(app, 'state') else 0

    health_response = {
        "ok": True,
        "ts": now_iso,
        "version": version,
        "region": region,
        "uptime_seconds": uptime_seconds,
        "db": None
    }

    # 强制设置不缓存
    response.headers["Cache-Control"] = "no-store"
    
    if not pool:
        from fastapi.responses import JSONResponse
        return JSONResponse(content=health_response, headers={"Cache-Control": "no-store"})
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        from fastapi.responses import JSONResponse
        return JSONResponse(content=health_response, headers={"Cache-Control": "no-store"})
    except Exception as e:
        health_response["ok"] = False
        health_response["db"] = f"{type(e).__name__}: {e}"
        from fastapi.responses import JSONResponse
        return JSONResponse(content=health_response, headers={"Cache-Control": "no-store"})