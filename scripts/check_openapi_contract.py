#!/usr/bin/env python3
import json, os, sys, urllib.request

BASE = os.environ.get("PORTPULSE_BASE_URL", "https://api.useportpulse.com")
OPENAPI_URL = f"{BASE}/openapi.json"

# 期望端点（可按需增补，但不减）
EXPECTED_PORTS = {
    "/v1/ports/{unlocode}/snapshot",
    "/v1/ports/{unlocode}/dwell",
    "/v1/ports/{unlocode}/overview",
    "/v1/ports/{unlocode}/alerts",
    "/v1/ports/{unlocode}/trend",
}
EXPECTED_META = {"/v1/health", "/v1/sources"}

def load_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read().decode("utf-8"))

def has_api_key_param(op: dict) -> bool:
    params = op.get("parameters") or []
    for p in params:
        if p.get("in") == "header" and p.get("name") in ("X-API-Key", "x-api-key"):
            return True
    return False

def main():
    d = load_json(OPENAPI_URL)
    paths = d.get("paths", {})
    existing = set(paths.keys())

    # 端点集合不应缺失
    missing = (EXPECTED_PORTS | EXPECTED_META) - existing
    if missing:
        print(f"❌ Missing paths in openapi: {sorted(missing)}")
        sys.exit(1)

    # 所有 /v1/ports/* 和 /v1/sources 需要能看到 X-API-Key
    to_check = [p for p in existing if p.startswith("/v1/ports/")] + ["/v1/sources"]
    bad = []
    for p in to_check:
        get = (paths.get(p, {}).get("get") or {})
        if not has_api_key_param(get):
            bad.append(p)
    if bad:
        print(f"❌ Missing X-API-Key param on: {sorted(bad)}")
        sys.exit(1)

    print("✅ OpenAPI contract ok")

if __name__ == "__main__":
    main()