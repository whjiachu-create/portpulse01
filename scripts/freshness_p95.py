import json, os, sys, urllib.request, datetime, statistics
BASE = os.environ.get("BASE","https://api.useportpulse.com")
CONF = sys.argv[1] if len(sys.argv)>1 else "ports_p1.yaml"

# 读 yaml 的简易法：让 yq 先转 JSON（如果无 yq，可改成 PyYAML）
import subprocess, shlex
raw = subprocess.check_output(shlex.split(f"yq -o=json {CONF}"))
ports = [p["unlocode"] for p in json.loads(raw)["ports"]]

ages=[]
now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
for u in ports:
    url = f"{BASE}/v1/ports/{u}/trend?days=3&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        pts = data.get("points") or []
        if not pts: continue
        # 兼容 date/ISO 时间两种
        t = pts[-1].get("date") or pts[-1].get("timestamp")
        if not t: continue
        if len(t) == 10:
            dt = datetime.datetime.fromisoformat(t).replace(tzinfo=datetime.timezone.utc)
        else:
            dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00"))
        age_h = (now - dt).total_seconds()/3600.0
        ages.append(age_h)
    except Exception:
        continue

if not ages:
    print("freshness_p95: no data")
    sys.exit(1)

p95 = statistics.quantiles(ages, n=100)[94]
p50 = statistics.median(ages)
print(json.dumps({"count":len(ages), "p50_h":round(p50,2), "p95_h":round(p95,2)}))
