#!/usr/bin/env python3
import sys, json, urllib.request, re, statistics, datetime
BASE=sys.argv[1] if len(sys.argv)>1 else "https://api.useportpulse.com"
ports=re.findall(r'unlocode:\s*([A-Z]{5})', open("ports_p1.yaml",encoding="utf-8").read())
delays=[]
now=datetime.datetime.now(datetime.timezone.utc)

def parse_dt(s:str):
    # 优先解析完整 ISO；退化到仅日期 -> 12:00Z 作为观测点
    s=s.strip()
    try:
        dt=datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        try:
            d=datetime.date.fromisoformat(s)
            return datetime.datetime(d.year,d.month,d.day,12,0,0,tzinfo=datetime.timezone.utc)
        except Exception:
            return None

for u in ports:
    try:
        with urllib.request.urlopen(f"{BASE}/v1/ports/{u}/trend?days=30", timeout=12) as r:
            pts=json.load(r).get("points",[])
        if not pts: 
            continue
        last=pts[-1].get("date")
        dt=parse_dt(str(last)) if last is not None else None
        if dt:
            delays.append((now-dt).total_seconds()/3600.0)
    except Exception:
        pass

p95=statistics.quantiles(delays, n=20)[18] if len(delays)>=20 else (max(delays) if delays else float("inf"))
print(f"ports={len(ports)}  samples={len(delays)}  p95_h={p95:.2f}")
sys.exit(0 if delays and p95<=2.0 else 1)
