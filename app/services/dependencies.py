import os
from fastapi import Header, HTTPException, status

_VALID = [k.strip() for k in os.getenv("PORTPULSE_API_KEYS", "dev_demo_123").split(",") if k.strip()]

def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    if not x_api_key or x_api_key not in _VALID:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key missing/invalid")
    return x_api_key
