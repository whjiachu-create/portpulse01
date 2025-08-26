import json, os, sys, urllib.request, datetime, statistics, yaml
BASE = os.environ.get("BASE","https://api.useportpulse.com")
CONF = sys.argv[1] if len(sys.argv)>1 else "ports_p1.yaml"
with open(CONF,"r") as f:
    ports=[p["unlocode"] for p in yaml.safe_load(f)["ports"]]
ages=[]; now=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
for u in ports:
    url=f"{BASE}/v1/ports/{u}/trend?days=3&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data=json.load(r)
        pts=data.get("points") or []
        if not pts: continue
        t=pts[-1].get("date") or pts[-1].get("timestamp")
        if not t: continue
        dt = (datetime.datetime.fromisoformat(t) if len(t)==10
              else datetime.datetime.fromisoformat(t.replace("Z","+00:00"))).replace(tzinfo=datetime.timezone.utc)
        ages.append((now-dt).total_seconds()/3600.0)
    except Exception: pass
if not ages: print("freshness_p95: no data"); sys.exit(1)
p95=statistics.quantiles(ages, n=100)[94]; p50=statistics.median(ages)
print(json.dumps({"count":len(ages),"p50_h":round(p50,2),"p95_h":round(p95,2)}))
