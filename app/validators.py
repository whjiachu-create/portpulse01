import re
from fastapi import HTTPException

_UNLOCODE_RE = re.compile(r"^[A-Z]{5}$")

# 你现有的港口目录查找函数/集合；示例：
try:
    from app.ports_catalog import KNOWN_PORTS  # e.g., set(["USLAX", "SGSIN", ...])
except Exception:
    KNOWN_PORTS = set()

def ensure_valid_unlocode(unlocode: str):
    if not _UNLOCODE_RE.match(unlocode or ""):
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_UNLOCODE_FORMAT",
            "message": "UN/LOCODE must be 5 uppercase letters",
            "request_id": "",
            "hint": "Example: USLAX, SGSIN"
        })
    if KNOWN_PORTS and unlocode not in KNOWN_PORTS:
        raise HTTPException(status_code=404, detail={
            "code": "UNLOCODE_NOT_FOUND",
            "message": f"Port {unlocode} not found",
            "request_id": "",
            "hint": "Check /v1/sources or coverage list"
        })
