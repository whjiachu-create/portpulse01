from fastapi import APIRouter, Depends, Path, Query, HTTPException
from asyncpg.connection import Connection
from datetime import date, datetime
from app.deps import get_conn

router = APIRouter(prefix="/hs", tags=["trade"])

def _parse_month_1st(s: str) -> date:
    # 期望 YYYY-MM-01；如果传 YYYY-MM 也自动补 -01
    if len(s) == 7:  # YYYY-MM
        s = s + "-01"
    try:
        d = date.fromisoformat(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date; expected YYYY-MM-01")
    if d.day != 1:
        raise HTTPException(status_code=400, detail="Date must be the first day of month (YYYY-MM-01)")
    return d

def _default_range_last_months(months: int = 6) -> tuple[date, date]:
    today = date.today().replace(day=1)
    # 简单以 30 天回退近似计算月初
    start = (datetime(today.year, today.month, 1) - (months * 30))  # type: ignore
    # 更稳妥地计算起始月份：
    y = today.year
    m = today.month - months
    while m <= 0:
        y -= 1
        m += 12
    start = date(y, m, 1)
    return (start, today)

@router.get("/{code}/imports")
async def hs_imports(
    code: str = Path(..., min_length=2, max_length=10, description="HS code, e.g. 4202"),
    country: str = Query("US", min_length=2, max_length=3, description="ISO2/ISO3，默认 US"),
    frm: str | None = Query(None, description="起始：YYYY-MM-01（默认最近 6 个月）"),
    to: str  | None = Query(None, description="结束：YYYY-MM-01（默认当月）"),
    conn: Connection = Depends(get_conn),
):
    """
    在 hs_imports 上按 code/country/period 过滤，按 period 升序返回。
    """
    if frm and to:
        frm_d = _parse_month_1st(frm)
        to_d  = _parse_month_1st(to)
        if frm_d > to_d:
            raise HTTPException(status_code=400, detail="frm must be <= to")
    else:
        frm_d, to_d = _default_range_last_months(6)

    rows = await conn.fetch("""
        SELECT period, value, origin, src, src_loaded_at
        FROM hs_imports
        WHERE code = $1
          AND country = $2
          AND period >= $3 AND period <= $4
        ORDER BY period ASC;
    """, code, country.upper(), frm_d, to_d)

    return {
        "code": code,
        "country": country.upper(),
        "frm": frm_d.isoformat(),
        "to": to_d.isoformat(),
        "items": [
            {
                "period": r["period"].isoformat(),
                "value": float(r["value"]) if r["value"] is not None else None,
                "origin": r["origin"],
                "src": r["src"],
                "src_loaded_at": r["src_loaded_at"].isoformat() if r["src_loaded_at"] else None,
            }
            for r in rows
        ]
    }