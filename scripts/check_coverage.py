import os, json, sys, urllib.request, yaml
BASE=os.environ.get("BASE","https://api.useportpulse.com")
CONF=sys.argv[1] if len(sys.argv)>1 else "ports_p1.yaml"
DAYS=int(os.environ.get("DAYS","30"))
with open(CONF,"r") as f:
    ports=[p["unlocode"] for p in yaml.safe_load(f)["ports"]]
ok=miss=0
print(f"{'PORT':8s}  points(>=25)")
for u in ports:
    try:
        with urllib.request.urlopen(f"{BASE}/v1/ports/{u}/trend?days={DAYS}") as r:
            n=len(json.load(r)["points"])
    except Exception:
        n=0
    if n>=25: ok+=1; print(f"{u:8s}  OK({n})")
    else: miss+=1; print(f"{u:8s}  MISS({n})")
print("---"); print(f"OK={ok}  MISS={miss}  TOTAL={len(ports)}")
sys.exit(0 if miss==0 else 1)
