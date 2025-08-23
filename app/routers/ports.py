from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from typing import Literal, List, Set, Optional
import hashlib
import time

from ..dependencies import require_api_key, get_conn  # 提供 X-API-Key 校验与 DB 连接

router = APIRouter()  # 仅此一个，全局唯一的 APIRouter 实例

CSV_SOURCE_TAG = "ports:overview:strong-etag"

def _csv_line(values: List[str]) -> str:
    return ",".join(values) + "\n"

def _strong_etag_from_text(text: str) -> str:
    return '"' + hashlib.sha256(text.encode("utf-8")).hexdigest() + '"'

def _client_etags(req: Request) -> Set[str]:
    inm = req.headers.get("if-none-match") or ""
    return {p.strip() for p in inm.split(",") if p.strip()}

def _etag_matches(etag: str, client_tags: Set[str]) -> bool:
    # 容忍弱标签 W/"..." 以及缺引号的极端情况
    norm = lambda s: s[2:].strip() if s.startswith("W/") else s.strip()
    a = norm(etag).strip('"')
    return any(a == norm(t).strip('"') for t in client_tags)

@router.get("/{unlocode}/overview")
async def port_overview(
    unlocode: str,
    request: Request,
    format: Literal["json", "csv"] = Query("json"),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):
    U = unlocode.upper()
    row = await conn.fetchrow(
        """
        SELECT snapshot_ts, vessels, avg_wait_hours, congestion_score, src, src_loaded_at
        FROM port_snapshots
        WHERE unlocode = $1
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        U,
    )

    # JSON 分支
    if format == "json":
        if not row:
            return {
                "unlocode": U,
                "as_of": None,
                "metrics": None,
                "source": None,
            }
        return {
            "unlocode": U,
            "as_of": row["snapshot_ts"],
            "metrics": {
                "vessels": int(row["vessels"]),
                "avg_wait_hours": float(row["avg_wait_hours"]),
                "congestion_score": float(row["congestion_score"]),
            },
            "source": {"src": row["src"], "src_loaded_at": row["src_loaded_at"]},
        }

    # CSV 分支
    header = _csv_line(["unlocode", "as_of", "vessels", "avg_wait_hours", "congestion_score"])
    if not row:
        body = _csv_line([U, "", "", "", ""])
    else:
        body = _csv_line([
            U,
            row["snapshot_ts"].isoformat(),
            str(int(row["vessels"])),
            f"{float(row['avg_wait_hours']):.2f}",
            f"{float(row['congestion_score']):.1f}",
        ])
    csv_text = header + body

    etag = _strong_etag_from_text(csv_text)
    if _etag_matches(etag, _client_etags(request)):
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
                "X-CSV-Source": CSV_SOURCE_TAG,
            },
        )

    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=300, no-transform",
            "Vary": "Accept-Encoding",
            "X-CSV-Source": CSV_SOURCE_TAG,
        },
    )