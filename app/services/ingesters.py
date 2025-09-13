# app/services/ingesters.py
from __future__ import annotations

import os, json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import httpx

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------
DATA_DIR = Path(os.getenv("INGEST_DATA_DIR", "data/overrides"))
PUBLIC_API_BASE = os.getenv("PUBLIC_API_BASE", "https://api.useportpulse.com")
WINDOW = int(os.getenv("INGEST_WINDOW_DAYS", "30"))
SEED_KEY = os.getenv("SEED_API_KEY", os.getenv("API_KEY", ""))  # 用现有 live key 作为种子抓取凭据


# --------------------------------------------------------------------
# Small JSON helpers
# --------------------------------------------------------------------
def _load_json(path: Path) -> Dict:
    """Load JSON if exists; otherwise a minimal overlay structure."""
    return json.loads(path.read_text()) if path.exists() else {"unlocode": None, "points": []}


def _save_json(path: Path, obj: Dict) -> None:
    """Persist JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


# --------------------------------------------------------------------
# Seed & normalize
# --------------------------------------------------------------------
async def _seed_from_public(port: str) -> Dict:
    """Pull /trend?window=WINDOW from public API to bootstrap overlay."""
    url = f"{PUBLIC_API_BASE}/v1/ports/{port}/trend?window={WINDOW}&format=json"
    headers = {"X-API-Key": SEED_KEY} if SEED_KEY else {}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()


def _normalize(points: List[Dict]) -> List[Dict]:
    """Dedupe-by-date, sort asc, keep the last WINDOW days."""
    dmap = {p["date"]: p for p in points}
    out = [dmap[k] for k in sorted(dmap)]
    if out:
        last = date.fromisoformat(out[-1]["date"])
        start = last - timedelta(days=WINDOW - 1)
        out = [p for p in out if date.fromisoformat(p["date"]) >= start]
    return out


# --------------------------------------------------------------------
# Public entry
# --------------------------------------------------------------------
async def ingest_port_day(port: str, day: date) -> Dict:
    """
    覆盖式写入：data/overrides/{PORT}/trend.json

    - 若无种子文件，先从线上 /trend?window=WINDOW 拉一份（用 SEED_API_KEY）
    - 覆盖/补齐目标日期一条记录（默认继承上一条的数值）
    - 标记 src=nowcast, as_of=now(UTC)
    """
    port = port.upper()
    path = DATA_DIR / port / "trend.json"

    # 1) 读/初始化
    obj = _load_json(path)
    if not path.exists():
        try:
            seed = await _seed_from_public(port)
            obj["unlocode"] = port
            obj["points"] = seed.get("points", [])
        except Exception:
            obj = {"unlocode": port, "points": []}
    else:
        obj.setdefault("unlocode", port)
        obj.setdefault("points", [])

    # 2) 覆盖/补齐目标日期
    day_s = day.isoformat()
    by_date = {p["date"]: p for p in obj["points"]}
    if day_s in by_date:
        p = by_date[day_s]
    else:
        base = obj["points"][-1] if obj["points"] else {
            "vessels": 80, "avg_wait_hours": 30.0, "congestion_score": 56, "src": "demo"
        }
        p = {
            "date": day_s,
            "vessels": base.get("vessels", 80),
            "avg_wait_hours": base.get("avg_wait_hours", 30.0),
            "congestion_score": base.get("congestion_score", 56),
            "src": base.get("src", "demo"),
        }
        obj["points"].append(p)

    p["src"] = "nowcast"
    p["as_of"] = datetime.now(timezone.utc).isoformat()

    # 3) 规范化并保存
    obj["points"] = _normalize(obj["points"])
    _save_json(path, obj)

    return {"port": port, "day": day_s, "points": len(obj["points"]), "file": str(path)}