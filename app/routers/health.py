from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["meta"])

@router.get("/health")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
