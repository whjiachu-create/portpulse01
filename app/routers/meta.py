from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(prefix="/v1", tags=["meta"])

@router.get("/health", summary="Liveness/Readiness")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
