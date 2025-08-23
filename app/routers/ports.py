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
