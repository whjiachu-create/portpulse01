# app/routers/ports.py
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Literal, Set
from datetime import datetime, date
from fastapi import Request
import hashlib
import time
CSV_SOURCE_TAG = "ports:overview:strong-etag"

# 导入或定义 get_conn 依赖
from ..dependencies import require_api_key, get_conn  # 确保 dependencies.py 中已定义并导出 require_api_key 和 get_conn

router = APIRouter(tags=["ports"])

# =========================
# Pydantic 模型（输出契约）
# =========================


# =========================
# 辅助函数
# =========================

def _csv_line(values: List[str]) -> str:
    # 简单 CSV（字段都为基础类型 & 无逗号）
    return ",".join(values) + "\n"

def _strong_etag_from_text(csv_text: str) -> str:
    # 以内容为准，生成稳定强 ETag（无 W/ 前缀，必须有双引号）
    digest = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    return f'"{digest}"'  # 强标签

def _client_etags(req: Request) -> Set[str]:
    inm = req.headers.get("if-none-match") or ""
    parts = [p.strip() for p in inm.split(",") if p.strip()]
    return set(parts)

def _etag_matches(strong_etag: str, client_tags: Set[str]) -> bool:
    """
    RFC 7232: If-None-Match 使用弱比较。这里既匹配强标签，也接受客户端发送的弱标签 W/"...".
    """
    return (strong_etag in client_tags) or (f'W/{strong_etag}' in client_tags)

# ---- 统一构造 overview CSV + 强 ETag ----
def _build_overview_csv(unlocode: str, row) -> tuple[str, str]:
    header = _csv_line(["unlocode", "as_of", "vessels", "avg_wait_hours", "congestion_score"])
    if not row:
        body = _csv_line([unlocode, "", "", "", ""])
    else:
        body = _csv_line([
            unlocode,
            row["snapshot_ts"].isoformat(),
            str(int(row["vessels"])),
            f"{float(row['avg_wait_hours']):.2f}",
            f"{float(row['congestion_score']):.1f}",
        ])
    csv_text = header + body
    etag = _strong_etag_from_text(csv_text)
    return csv_text, etag

# =========================
# 端点：Snapshot（永不顶层 null）
# =========================


# =========================
# 端点：Overview（json/csv）
# =========================

@router.get(
    "/{unlocode}/overview",
    summary="Port Overview",
    tags=["ports"],
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "unlocode": "USLAX",
                        "as_of": "2025-08-14T13:20:02.240670Z",
                        "metrics": {
                            "vessels": 160,
                            "avg_wait_hours": 3.92,
                            "congestion_score": 60.0
                        },
                        "source": {"src": "prod", "src_loaded_at": "2025-08-14T13:20:02.240670Z"}
                    }
                }
            }
        }
    },
)
async def port_overview(
    unlocode: str,
    request: Request,  # 添加 request 参数以获取 headers
    format: Literal["json", "csv"] = Query("json", description="返回格式"),
    _auth: None = Depends(require_api_key),
    conn=Depends(get_conn),
):

    """
    用最新一条 snapshot 作为该港口的概览。
    - JSON：返回 as_of + metrics + source
    - CSV：返回一行标题 + 一行数据
    """
    U = unlocode.upper()

    # 如果是 CSV 格式，先检查缓存（若有）
    if format == "csv":
        cache_key = f"overview_csv:{U}"
        if hasattr(request.app.state, 'cache'):
            cached_response = request.app.state.cache.get(cache_key)
            if cached_response:
                # 过期即丢弃（TTL 60s）
                if time.time() - cached_response.get("timestamp", 0) > 60:
                    request.app.state.cache.pop(cache_key, None)
                else:
                    # 始终用内容重新计算强 ETag
                    etag = _strong_etag_from_text(cached_response["content"])
                    client_tags = _client_etags(request)
                    if _etag_matches(etag, client_tags):
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
                        content=cached_response["content"],
                        media_type="text/csv; charset=utf-8",
                        headers={
                            "ETag": etag,
                            "Cache-Control": "public, max-age=300, no-transform",
                            "Vary": "Accept-Encoding",
                            "X-CSV-Source": CSV_SOURCE_TAG,
                        },
                    )

    start_time = time.time()
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

    if format == "csv":
        # 生成 CSV 与强 ETag，并检查 If-None-Match（兼容弱标签 W/"..."）
        csv_string, etag = _build_overview_csv(U, row)
        client_tags = _client_etags(request)
        if _etag_matches(etag, client_tags):
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": "public, max-age=300, no-transform",
                    "Vary": "Accept-Encoding",
                    "X-CSV-Source": CSV_SOURCE_TAG,
                }
            )

        # 记录耗时
        process_time = time.time() - start_time
        print(f"CSV generation for {U} took {process_time*1000:.2f}ms")

        # 如果处理时间超过800ms，则缓存结果60秒
        if process_time > 0.8:
            if not hasattr(request.app.state, 'cache'):
                request.app.state.cache = {}

            # 设置缓存，记录生成时间戳
            request.app.state.cache[f"overview_csv:{U}"] = {
                "content": csv_string,
                "etag": etag,
                "timestamp": time.time()
            }

            # 清理过期缓存（可选）
            expired_keys = []
            for key, value in request.app.state.cache.items():
                if time.time() - value["timestamp"] > 60:
                    expired_keys.append(key)
            for key in expired_keys:
                del request.app.state.cache[key]

        return PlainTextResponse(
            content=csv_string,
            media_type="text/csv; charset=utf-8",
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, no-transform",
                "Vary": "Accept-Encoding",
                "X-CSV-Source": CSV_SOURCE_TAG,
            }
        )

    # JSON
    if not row:
        response = OverviewResponse(unlocode=U, as_of=None, metrics=None, source=None)
        return response

    response = OverviewResponse(
        unlocode=U,
        as_of=row["snapshot_ts"],
        metrics={
            "vessels": int(row["vessels"]),
            "avg_wait_hours": float(row["avg_wait_hours"]),
            "congestion_score": float(row["congestion_score"]),
        },
        source=OverviewSource(
            src=row["src"],
            src_loaded_at=row["src_loaded_at"],
        ),
    )
    return response

## 删除未使用的重复实现：get_port_overview_csv

# =========================
# 端点：Alerts（基于 dwell 的窗口对比）
# =========================


# =========================
# 端点：Trend（支持 fields/分页；基于 snapshots 按天聚合）
# =========================
