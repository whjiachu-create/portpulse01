from fastapi import APIRouter
from datetime import datetime, timezone
import os

router = APIRouter(prefix="/v1", tags=["meta"])

@router.get("/health", summary="Liveness/Readiness")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/meta/sources", summary="Data sources & ETL metadata")
def meta_sources():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "sources": [
            {"name": "demo", "type": "synthetic", "freshness": "PT30M", "last_updated": "2025-09-17T00:00:00Z"}
        ],
        "etl": {"window": "hourly", "retries": 2, "backfill": "30d"},
        "build": {
            "version": os.getenv("PORTPULSE_VERSION", "0.1.1"),
            "commit": os.getenv("PORTPULSE_COMMIT")
        },
        "updated_at": now.isoformat()
    }
