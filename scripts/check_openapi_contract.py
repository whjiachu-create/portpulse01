#!/usr/bin/env python3
import json, os, sys, urllib.request

BASE = os.environ.get("PORTPULSE_BASE_URL", "https://api.useportpulse.com")
# 兜底直连 Railway（你的当前生产子域）——如后续子域变化，再改这里或用环境变量覆盖
RAW  = os.environ.get("PORTPULSE_RAW_URL",  "https://portpulse01-production-97fa.up.railway.app")

def fetch(url: str):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)

def get_openapi():
    try:
        return fetch(f"{BASE}/openapi.json")
    except Exception:
        return fetch(f"{RAW}/openapi.json")

def main():
    doc = get_openapi()
    paths = set(doc.get("paths", {}).keys())
    need = {
        "/v1/ports/{unlocode}/trend",
        "/v1/ports/{unlocode}/dwell",
        "/v1/ports/{unlocode}/snapshot",
    }
    miss = sorted(need - paths)
    if miss:
        print("Missing paths:", miss); sys.exit(2)
    print("OpenAPI contract OK")

if __name__ == "__main__":
    main()
