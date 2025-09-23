from datetime import datetime, timezone
from fastapi import APIRouter

# Health endpoint MUST NEVER 500.
router = APIRouter(prefix="/v1", tags=["meta"])

@router.get("/health")
def health():
    try:
        # 不做外部依赖调用；保持常数时间
        return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        # 即便出现意外也保持 200
        return {"ok": False, "ts": datetime.now(timezone.utc).isoformat()}
