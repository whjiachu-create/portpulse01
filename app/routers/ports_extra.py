# app/routers/ports_extra.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
import asyncpg
import io, csv

from app.main import pool  # 复用全局连接池
from app.deps import require_api_key  # 你现有的鉴权依赖

router = APIRouter(prefix="/v1/ports", tags=["ports+"])

# —— 小工具：把 list[dict] 转 CSV —— #
def _to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    # 统一字段顺序
    cols = list(rows[0].keys())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in cols})
    return buf.getvalue()

# —— 映射：UN/LOCODE -> meta_sources 里的 name 关键字 —— #
_PORT_SOURCE_HINTS = {
    "USLAX": "Los Angeles",
    "USNYC": "New York",
}

async def _fetch_source_meta(conn: asyncpg.Connection, unlocode: str) -> Dict[str, Any]:
    hint = _PORT_SOURCE_HINTS.get(unlocode, "")
    if not hint:
        return {}
    row = await conn.fetchrow(
        """SELECT id, name, url, last_updated
           FROM meta_sources
           WHERE name ILIKE '%'||$1||'%'
           ORDER BY id LIMIT 1""",
        hint,
    )
    if not row:
        return {}
    return dict(row)

@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    request: Request,
    format: Optional[str] = Query(None, description="csv 可导出为 CSV"),
    _=Depends(require_api_key),
):
    """
    汇总一个港口：今日快照 + 7 日趋势 + 简单异常提示（基于 90 日分位）
    不改表，仅在查询层做聚合与计算。
    """
    async with pool.acquire() as conn:
        # 1) 最新快照
        snap = await conn.fetchrow(
            """
            SELECT unlocode, snapshot_ts, vessels, avg_wait_hours, congestion_score, src
            FROM port_snapshots
            WHERE unlocode = $1
            ORDER BY snapshot_ts DESC
            LIMIT 1
            """,
            unlocode,
        )
        if not snap:
            raise HTTPException(status_code=404, detail="No snapshot")

        # 2) 计算 7 日趋势（以 dwell 的最大日期为准）
        md = await conn.fetchval(
            "SELECT COALESCE(MAX(date), CURRENT_DATE) FROM port_dwell WHERE unlocode=$1",
            unlocode,
        )
        # 时间窗口
        last7_from = md - timedelta(days=6)
        prev7_from = md - timedelta(days=13)
        prev7_to = md - timedelta(days=7)

        row = await conn.fetchrow(
            """
            WITH dw AS (
              SELECT date, dwell_hours FROM port_dwell WHERE unlocode=$1
            )
            SELECT
              (SELECT AVG(dwell_hours) FROM dw WHERE date BETWEEN $2 AND $3) AS avg_last7,
              (SELECT AVG(dwell_hours) FROM dw WHERE date BETWEEN $4 AND $5) AS avg_prev7
            """,
            unlocode, last7_from, md, prev7_from, prev7_to,
        )
        avg_last7 = row["avg_last7"] or 0.0
        avg_prev7 = row["avg_prev7"] or 0.0
        change_pct = ((avg_last7 - avg_prev7) / avg_prev7 * 100.0) if avg_prev7 else None
        direction = (
            "rising" if (change_pct is not None and change_pct >= 5.0)
            else "falling" if (change_pct is not None and change_pct <= -5.0)
            else "stable"
        )

        # 3) 90 日 p80 阈值做一个“异常”提示
        p80 = await conn.fetchval(
            """
            SELECT percentile_cont(0.8) WITHIN GROUP (ORDER BY dwell_hours)
            FROM port_dwell
            WHERE unlocode=$1 AND date >= CURRENT_DATE - INTERVAL '90 days'
            """,
            unlocode,
        )
        alerts = []
        if p80 is not None and snap["avg_wait_hours"] is not None:
            if snap["avg_wait_hours"] > float(p80):
                alerts.append({
                    "type": "surge",
                    "message": "Wait hours > p80 vs 90d baseline"
                })

        # 4) meta_sources 做“可审计四件套”
        meta = await _fetch_source_meta(conn, unlocode)

        payload = {
            "unlocode": unlocode,
            "snapshot": {
                "as_of": snap["snapshot_ts"],
                "vessels": snap["vessels"],
                "avg_wait_hours": snap["avg_wait_hours"],
                "congestion_score": snap["congestion_score"],
                "score_breakdown": {
                    # 先放一个可解释占比，后续可以在后端参数化
                    "wait_hours": 0.6, "vessel_count": 0.3, "anchorage_ratio": 0.1
                },
                "source_name": meta.get("name"),
                "source_url": meta.get("url"),
                "method": "official_publication",   # 或 "modeled_from_AIS" 等
                "src_loaded_at": snap["snapshot_ts"],
            },
            "trend_7d": {
                "avg_dwell": avg_last7,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "direction": direction,
                "window_end": md,
            },
            "alerts": alerts,
            "score_model_version": "v1.0"
        }

        # CSV 导出（把 snapshot 扁平化一下）
        if (format or "").lower() == "csv":
            rows = [{
                "unlocode": payload["unlocode"],
                "as_of": str(payload["snapshot"]["as_of"]),
                "vessels": payload["snapshot"]["vessels"],
                "avg_wait_hours": payload["snapshot"]["avg_wait_hours"],
                "congestion_score": payload["snapshot"]["congestion_score"],
                "trend_7d_avg": payload["trend_7d"]["avg_dwell"],
                "trend_7d_change_pct": payload["trend_7d"]["change_pct"],
                "trend_7d_direction": payload["trend_7d"]["direction"],
                "source_name": payload["snapshot"]["source_name"],
                "source_url": payload["snapshot"]["source_url"],
                "method": payload["snapshot"]["method"],
                "score_model_version": payload["score_model_version"],
            }]
            csv_text = _to_csv(rows)
            return (
                csv_text
            )

        return payload


@router.get("/{unlocode}/alerts")
async def port_alerts(
    unlocode: str,
    window: str = Query("7d", pattern="^(7d|14d|30d)$"),
    request: Request = None,
    format: Optional[str] = Query(None, description="csv 可导出为 CSV"),
    _=Depends(require_api_key),
):
    """
    输出信号而不是原始数：趋势标签 + 拥堵状态等
    """
    days = int(window.replace("d", ""))
    async with pool.acquire() as conn:
        md = await conn.fetchval(
            "SELECT COALESCE(MAX(date), CURRENT_DATE) FROM port_dwell WHERE unlocode=$1",
            unlocode,
        )
        from_day = md - timedelta(days=days-1)
        prev_from = from_day - timedelta(days=days)
        prev_to = from_day - timedelta(days=1)

        row = await conn.fetchrow(
            """
            WITH dw AS (
              SELECT date, dwell_hours FROM port_dwell WHERE unlocode=$1
            )
            SELECT
              (SELECT AVG(dwell_hours) FROM dw WHERE date BETWEEN $2 AND $3) AS avg_win,
              (SELECT AVG(dwell_hours) FROM dw WHERE date BETWEEN $4 AND $5) AS avg_prev
            """,
            unlocode, from_day, md, prev_from, prev_to
        )
        avg_win = row["avg_win"] or 0.0
        avg_prev = row["avg_prev"] or 0.0
        change_pct = ((avg_win - avg_prev) / avg_prev * 100.0) if avg_prev else None
        label = (
            "rising" if (change_pct is not None and change_pct >= 5.0)
            else "falling" if (change_pct is not None and change_pct <= -5.0)
            else "stable"
        )

        # 拥堵状态：用 90 日 p75/p90 打一个简易等级
        p75, p90 = await conn.fetchrow(
            """
            SELECT
              percentile_cont(0.75) WITHIN GROUP (ORDER BY dwell_hours),
              percentile_cont(0.90) WITHIN GROUP (ORDER BY dwell_hours)
            FROM port_dwell
            WHERE unlocode=$1 AND date >= CURRENT_DATE - INTERVAL '90 days'
            """,
            unlocode,
        )

        congestion = "normal"
        reason = None
        if p90 is not None and avg_win > float(p90):
            congestion, reason = "severe", "avg_dwell > p90 (90d)"
        elif p75 is not None and avg_win > float(p75):
            congestion, reason = "elevated", "avg_dwell > p75 (90d)"

        signals = [
            {
                "name": "dwell_trend",
                "label": label,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "confidence": 0.8 if label != "stable" else 0.6
            },
            {
                "name": "congestion",
                "label": congestion,
                "reason": reason
            }
        ]

        out = {
            "unlocode": unlocode,
            "window": window,
            "signals": signals,
            "window_end": md
        }

        if (format or "").lower() == "csv":
            # 展平为多行
            rows = []
            for s in signals:
                rows.append({
                    "unlocode": unlocode,
                    "window": window,
                    "name": s["name"],
                    "label": s["label"],
                    "change_pct": s.get("change_pct"),
                    "reason": s.get("reason"),
                    "window_end": str(md),
                })
            return _to_csv(rows)

        return out