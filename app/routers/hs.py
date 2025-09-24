from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["hs"])

@router.get("/{hs_code}/imports", summary="HS Imports (beta-gated)")
def hs_imports_beta(hs_code: str, from_: str | None = None, to: str | None = None, format: str | None = None):
    # 功能未启用：按验收要求 → 4xx（403更贴切），并让全局异常处理器统一成四字段
    raise HTTPException(
        status_code=403,
        detail={
            "code": "beta_disabled",
            "message": "HS imports API is not enabled on this environment",
            "hint": "Contact support to enable beta access",
        },
    )


# --- Alias: /v1/hs/{code}/imports  (kept for OpenAPI contract & acceptance) ---
from fastapi import HTTPException, Query, Request

@router.get("/{code}/imports", summary="HS imports (alias for acceptance)")
async def hs_imports_alias(
    code: str,
    request: Request,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    format: str | None = Query(None, pattern="^(json|csv)$")
):
    # 与主路由一致：当前环境未启用，返回 403 + 统一错误体字段
    raise HTTPException(
        status_code=403,
        detail={
            "code": "beta_disabled",
            "message": "HS imports API is not enabled on this environment",
            "hint": "Contact support to enable beta access"
        }
    )
