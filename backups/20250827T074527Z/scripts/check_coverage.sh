#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://api.useportpulse.com}"
CONF="${1:-ports_p1.yaml}"
DAYS="${DAYS:-30}"
python3 - "$BASE" "$CONF" "$DAYS" <<'PY'
import sys, json, urllib.request, re
BASE, CONF, DAYS = sys.argv[1], sys.argv[2], sys.argv[3]
# 极简 YAML 解析（只抓 UN/LOCODE）
txt=open(CONF,encoding="utf-8").read()
ports=re.findall(r'unlocode:\s*([A-Z]{5})',txt)
ok=miss=0
print(f'{"PORT":8}  points(>=25)')
for u in ports:
    try:
        with urllib.request.urlopen(f"{BASE}/v1/ports/{u}/trend?days={DAYS}", timeout=10) as r:
            n=len(json.load(r).get("points",[]))
    except Exception: n=0
    if n>=25: print(f'{u:8}  OK({n})'); ok+=1
    else:     print(f'{u:8}  MISS({n})'); miss+=1
print('---'); print(f'OK={ok}  MISS={miss}  TOTAL={len(ports)}')
sys.exit(0 if miss==0 else 1)
PY
