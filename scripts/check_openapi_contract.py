#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的 OpenAPI 契约检查器：
- 校验关键路径是否存在
- 校验常用参数是否在文档中声明
失败即退出码非 0，CI 会标红
"""
import json, sys, urllib.request, os

BASE = os.getenv("PORTPULSE_BASE_URL", "https://api.useportpulse.com")
OPENAPI = f"{BASE}/openapi.json"

REQUIRED_PATHS = [
    "/v1/health",
    "/v1/sources",
    "/v1/ports/{unlocode}/snapshot",
    "/v1/ports/{unlocode}/dwell",
    "/v1/ports/{unlocode}/overview",
    "/v1/ports/{unlocode}/alerts",
    "/v1/ports/{unlocode}/trend",
]

def get_openapi():
    req = urllib.request.Request(OPENAPI, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def main():
    doc = get_openapi()
    paths = doc.get("paths", {})
    missing = [p for p in REQUIRED_PATHS if p not in paths]
    if missing:
        print("❌ Missing paths:", missing)
        sys.exit(2)
    # 额外示例：校验 snapshot 的 path 参数 unlocode 是否声明
    snap = paths["/v1/ports/{unlocode}/snapshot"]["get"]
    params = [p["name"] for p in snap.get("parameters", [])]
    if "unlocode" not in params:
        print("❌ snapshot 未声明 path 参数 unlocode")
        sys.exit(3)
    print("✅ OpenAPI contract OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())