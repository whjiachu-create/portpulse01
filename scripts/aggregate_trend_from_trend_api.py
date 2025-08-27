#!/usr/bin/env python3
import os, re, json, urllib.request, datetime, pathlib, sys

BASE = os.environ.get("BASE", "https://api.useportpulse.com")
ports = re.findall(r'unlocode:\s*([A-Z]{5})', open("ports_p1.yaml", encoding="utf-8").read())
outdir = pathlib.Path("data/derived/trend"); outdir.mkdir(parents=True, exist_ok=True)

now_dt = datetime.datetime.now(datetime.timezone.utc)
now_iso = now_dt.isoformat()
today   = now_dt.date()

ok = miss = 0
for u in ports:
    try:
        with urllib.request.urlopen(f"{BASE}/v1/ports/{u}/trend?days=30", timeout=30) as r:
            resp = json.load(r)
    except Exception as e:
        print(f"[skip] {u}: {e}")
        miss += 1
        continue

    pts = resp.get("points", [])
    if not pts:
        out = {"unlocode": u, "points": []}
    else:
        last = pts[-1]
        # 解析最后一行日期
        d_last = None
        try:
            d_last = datetime.date.fromisoformat(str(last.get("date","")).strip())
        except Exception:
            pass

        # 给最后一行补 as_of（不改数值）
        pts[-1] = {**last, "as_of": now_iso, "src": last.get("src","api")}

        # 若最后一行是昨天或更早，则追加“今日软 nowcast”一行（用昨天的值，但 as_of=现在）
        if d_last is not None and d_last < today:
            soft = {
                "date": today.isoformat(),
                "vessels": last.get("vessels"),
                "avg_wait_hours": last.get("avg_wait_hours"),
                "congestion_score": last.get("congestion_score"),
                "src": "nowcast",
                "as_of": now_iso
            }
            pts.append(soft)

        out = {"unlocode": u, "points": pts[-30:]}  # 只保留 30 天

    path = outdir / f"{u}.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    ok += 1

print(f"wrote={ok} miss={miss}")
