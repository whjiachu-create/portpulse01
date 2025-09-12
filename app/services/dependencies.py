# app/services/dependencies.py

from __future__ import annotations
import os, json
from typing import Optional, Sequence, Iterable
from fastapi import Header, HTTPException

# ------------ helpers ------------

def _normalize_keys(items: Iterable[str]) -> Sequence[str]:
    """去重 + 去引号 + strip，保序"""
    seen = set()
    out = []
    for k in items:
        if k is None:
            continue
        k = str(k).strip().strip('"').strip("'")
        if not k:
            continue
        if k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)

def _coerce_list(value: str) -> Sequence[str]:
    """把任意形式（纯文本/分隔符/JSON）规范化成 key 列表"""
    if not value or not value.strip():
        return ()
    raw = value.strip()

    # JSON 数组或对象
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return _normalize_keys(data)
            if isinstance(data, dict):
                acc = []
                for v in data.values():
                    if isinstance(v, list):
                        acc.extend(v)
                    elif isinstance(v, str):
                        acc.append(v)
                return _normalize_keys(acc)
        except Exception:
            # 解析失败则按纯文本继续走
            pass

    # 常见分隔符：逗号/换行/空格/分号/Tab
    for sep in [",", "\n", ";", "\t", " "]:
        raw = raw.replace(sep, ",")
    return _normalize_keys(x for x in raw.split(",") if x)

def _keys_from_env() -> Sequence[str]:
    """
    读取可用 API keys（容错版）：
      - NEXT_PUBLIC_DEMO_API_KEY（单个或误配为列表/JSON）
      - API_KEYS（推荐；支持 CSV/空格/换行/JSON）
      - 兼容别名：API_KEYS__LIVE / API_KEYS__DEMO / PP_LIVE_KEYS
    """
    keys = []
    keys += _coerce_list(os.getenv("NEXT_PUBLIC_DEMO_API_KEY", ""))
    keys += _coerce_list(os.getenv("API_KEYS", ""))
    # 常见误名，做兼容
    keys += _coerce_list(os.getenv("API_KEYS__LIVE", ""))
    keys += _coerce_list(os.getenv("API_KEYS__DEMO", ""))
    keys += _coerce_list(os.getenv("PP_LIVE_KEYS", ""))
    return _normalize_keys(keys)

DEBUG = os.getenv("DEBUG_AUTH") == "1"
REQUIRE = os.getenv("REQUIRE_API_KEY", "1").lower() not in ("0", "false", "no")

if DEBUG:
    print("[BOOT] API_KEYS(raw) =", repr(os.getenv("API_KEYS")))
    print("[BOOT] API_KEYS__LIVE(raw) =", repr(os.getenv("API_KEYS__LIVE")))
    print("[BOOT] API_KEYS__DEMO(raw) =", repr(os.getenv("API_KEYS__DEMO")))
    print("[BOOT] PP_LIVE_KEYS(raw) =", repr(os.getenv("PP_LIVE_KEYS")))
    print("[BOOT] NEXT_PUBLIC_DEMO_API_KEY =", repr(os.getenv("NEXT_PUBLIC_DEMO_API_KEY")))
    print("[BOOT] REQUIRE_API_KEY =", REQUIRE)
    print("[BOOT] ALLOWLIST =", _keys_from_env())

# ------------ dependency ------------

def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> str:
    """
    简单 Header 鉴权：
      - 首选 X-API-Key: <key>
      - 兼容 Authorization: Bearer <key> 或 Authorization: <key>
      - REQUIRE_API_KEY=0 时旁路
    """
    if not REQUIRE:
        if DEBUG:
            print("[AUTH] bypass (REQUIRE_API_KEY=0)")
        return x_api_key or ""

    # 解析出最终 key
    key = (x_api_key or "").strip()
    if not key and authorization:
        a = authorization.strip()
        key = a[7:].strip() if a.lower().startswith("bearer ") else a

    allow = _keys_from_env()

    if DEBUG:
        print("[AUTH] got X-API-Key =", repr(x_api_key))
        print("[AUTH] got Authorization =", repr(authorization))
        print("[AUTH] resolved key =", repr(key))
        print("[AUTH] allowlist =", allow)

    if not key or key not in allow:
        if DEBUG:
            print("[AUTH] result = REJECT")
        raise HTTPException(status_code=401, detail="API key missing/invalid")

    if DEBUG:
        print("[AUTH] result = ALLOW")
    return key