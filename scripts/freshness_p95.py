#!/usr/bin/env python3
import sys, json, urllib.request, re, statistics, datetime
BASE=sys.argv[1] if len(sys.argv)>1 else "https://api.useportpulse.com"
ports=re.findall(r'unlocode:\s*([A-Z]{5})', open("ports_p1.yaml",encoding="utf-8").read())
delays=[]
now=datetime.datetime.now(datetime.timezone.utc)

def parse_dt(s):
    s=str(s).strip()
    try:
        dt=datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except: pass
    try:
        d=datetime.date.fromisoformat(s)
        return datetime.datetime(d.year,d.month,d.day,12,0,0,tzinfo=datetime.timezone.utc)
    except: return None

def jget(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)

for u in ports:
    dt=None
    try:
        import json, urllib.request, datetime
        with urllib.request.urlopen(f"{BASE}/v1/ports/{u}/trend?days=30", timeout=12) as r:
            pts=json.load(r).get("points",[])
        if pts:
            last=pts[-1]
            cand=last.get("as_of") or last.get("date")
            if cand:
                # 解析 ISO；若仅有日期则取当天 12:00Z
                s=str(cand).strip()
                try:
                    dt=datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
                    if not dt.tzinfo: dt=dt.replace(tzinfo=datetime.timezone.utc)
                except Exception:
                    try:
                        d=datetime.date.fromisoformat(s)
                        dt=datetime.datetime(d.year,d.month,d.day,12,0,0,tzinfo=datetime.timezone.utc)
                    except Exception:
                        dt=None
    except Exception:
        dt=None
    if dt:
        h=(now-dt).total_seconds()/3600.0
        delays.append(max(0.0, h))

p95=statistics.quantiles(delays, n=20)[18] if len(delays)>=20 else (max(delays) if delays else float("inf"))
print(f"ports={len(ports)}  samples={len(delays)}  p95_h={p95:.2f}")
sys.exit(0 if delays and p95<=2.0 else 1)
