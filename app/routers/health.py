from datetime import datetime, timezone
from fastapi import APIRouter

# NOTE: 这个路由本身不依赖任何外部资源，避免启动失败或阻塞。
router = APIRouter(prefix="/v1", tags=["meta"])

@router.get("/health")
def health():
    try:
        return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        # 极端情况下也要 200
        return {"ok": False, "ts": datetime.now(timezone.utc).isoformat()}
