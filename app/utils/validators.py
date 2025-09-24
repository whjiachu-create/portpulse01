from __future__ import annotations
import re
from fastapi import HTTPException

CORE_PORTS = {
    "USLAX","USLGB","USNYC","USSAV","USCHS","USORF","USHOU","USSEA","USOAK","USMIA",
    "NLRTM","BEANR","DEHAM","DEBRV","FRLEH","GBFXT","GBLGP","ESVLC","ESALG","GRPIR",
    "CNSHA","CNNGB","CNSZX","CNTAO","KRPUS","SGSIN","MYTPP","THLCH","INNSA","INMUN"
}
_UNLOCODE_RE = re.compile(r"^[A-Z]{5}$")

def validate_unlocode_or_raise(unlocode: str) -> str:
    """A) 格式非法 -> 422；B) 格式合法但不存在 -> 404；返回大写 UNLOCODE。"""
    u = (unlocode or "").upper()
    if not _UNLOCODE_RE.match(u):
        raise HTTPException(status_code=422, detail="invalid UNLOCODE format (A-Z x5)")
    if u not in CORE_PORTS:
        raise HTTPException(status_code=404, detail="port not found")
    return u
