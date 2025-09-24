import re
from typing import Optional, Set
from fastapi import HTTPException

_UNLOCODE_RE = re.compile(r"^[A-Z]{5}$")

def ensure_valid_unlocode(unlocode: str, catalog: Optional[Set[str]] = None) -> str:
    u = (unlocode or "").upper()
    if not _UNLOCODE_RE.match(u):
        raise HTTPException(status_code=422, detail="invalid UNLOCODE format (A-Z x5)")
    if catalog is not None and u not in catalog:
        raise HTTPException(status_code=404, detail="port not found")
    return u
