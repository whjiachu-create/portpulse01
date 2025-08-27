#!/usr/bin/env python3
import csv, sys, json, datetime, pathlib, statistics, collections
# 输入：data/port_calls/*.csv
# 输出：data/derived/dwell/{UNLOCODE}.json （{"unlocode":u,"points":[{"date":"YYYY-MM-DD","dwell_hours":x,"src":"vendor"}]}）
src="vendor"
def hours(a,b):
    if not a or not b: return None
    ta=datetime.datetime.fromisoformat(a.replace("Z","+00:00"))
    tb=datetime.datetime.fromisoformat(b.replace("Z","+00:00"))
    return max((tb-ta).total_seconds()/3600.0, 0.0)
daily=collections.defaultdict(lambda: collections.defaultdict(list))
for p in pathlib.Path("data/port_calls").glob("*.csv"):
    with open(p,encoding="utf-8") as f:
        r=csv.DictReader(f)
        for row in r:
            u=(row.get("unlocode") or "").strip().upper()
            dh=hours(row.get("arrived_utc"), row.get("departed_utc"))
            if not u or dh is None: continue
            d=datetime.datetime.fromisoformat(row["arrived_utc"].replace("Z","+00:00")).date().isoformat()
            daily[u][d].append(dh)
outdir=pathlib.Path("data/derived/dwell"); outdir.mkdir(parents=True, exist_ok=True)
for u, days in daily.items():
    pts=[]
    for d, vals in sorted(days.items()):
        pts.append({"date":d, "dwell_hours": round(statistics.median(vals),2), "src": src})
    with open(outdir/f"{u}.json","w",encoding="utf-8") as f:
        json.dump({"unlocode":u,"points":pts}, f, ensure_ascii=False)
    print(f"Wrote {outdir}/{u}.json ({len(pts)} pts)")
