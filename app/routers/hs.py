# app/routers/hs.py
from fastapi import APIRouter, Depends, Path, Query
from asyncpg.connection import Connection
from asyncpg import UndefinedTableError
from app.deps import get_conn

router = APIRouter()

@router.get("/hs/{code}/imports")
async def hs_imports(
    code: str = Path(..., min_length=2, max_length=10, description="HS code (2-10 digits)"),
    year: int | None = Query(None, description="Optional: filter by year"),
    limit: int = Query(50, ge=1, le=500),
    conn: Connection = Depends(get_conn),
):
    """
    返回 HS 进口明细/汇总。
    默认查询表: hs_imports(code, year, month, value, origin)
    - 如需聚合：SUM(value) GROUP BY year 或 month。
    """
    try:
        if year is None:
            rows = await conn.fetch("""
                SELECT year, month, value, origin
                FROM hs_imports
                WHERE code = $1
                ORDER BY year DESC, month DESC
                LIMIT $2
            """, code, limit)
        else:
            rows = await conn.fetch("""
                SELECT year, month, value, origin
                FROM hs_imports
                WHERE code = $1 AND year = $2
                ORDER BY month DESC
                LIMIT $3
            """, code, year, limit)

        return {
            "code": code,
            "items": [
                {"year": r["year"], "month": r["month"], "value": r["value"], "origin": r["origin"]}
                for r in rows
            ],
        }
    except UndefinedTableError:
        return {"error": "table 'hs_imports' not found", "code": code}