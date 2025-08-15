# app/deps.py
import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

# 让 FastAPI 知道这是一个“安全方案”，Swagger 才会出现 Authorize
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# 读环境变量（Railway/本地都可），默认 dev_key_123
API_KEY = os.getenv("API_KEYS") or os.getenv("API_KEY") or "dev_key_123"

def require_api_key(api_key: str = Security(api_key_scheme)) -> str:
    if not api_key or api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key