from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
import hashlib
from ..dependencies import get_conn, require_api_key

router = APIRouter()

def _etag_matches(etag: str, if_none_match: str) -> bool:
    # 移除引号并处理弱ETag前缀
    etag = etag.strip('"')
    if_none_match = if_none_match.strip('"').removeprefix('W/')
    return etag == if_none_match

@router.get("/v1/ports/overview.csv", dependencies=[Depends(require_api_key)])
async def get_port_overview_csv(
    request: Request,
    response: Response,
    conn=Depends(get_conn)
):
    # 获取数据
    rows = await conn.fetch("""
        SELECT port_id, port_name, country, service_count, latest_week
        FROM port_overview
        ORDER BY port_name
    """)
    
    # 生成CSV内容
    csv_content = "port_id,port_name,country,service_count,latest_week\n"
    for row in rows:
        csv_content += f"{row['port_id']},{row['port_name']},{row['country']},{row['service_count']},{row['latest_week']}\n"
    
    # 计算ETag
    etag = hashlib.sha256(csv_content.encode()).hexdigest()
    quoted_etag = f'"{etag}"'
    
    # 检查If-None-Match头
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and _etag_matches(quoted_etag, if_none_match):
        return Response(status_code=304)
    
    # 设置响应头
    response.headers["ETag"] = quoted_etag
    response.headers["Cache-Control"] = "public, max-age=300, no-transform"
    response.headers["Vary"] = "Accept-Encoding"
    response.headers["X-CSV-Source"] = "ports:overview:strong-etag"
    
    return PlainTextResponse(content=csv_content, media_type="text/csv")
