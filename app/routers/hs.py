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
