# app/services/overrides.py
from __future__ import annotations
import os, json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 兼容环境变量；未设置时使用项目内默认目录
DATA_DIR = Path(os.getenv("INGEST_DATA_DIR", "data/overrides"))

def _safe_load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _sort_points(points: List[Dict]) -> List[Dict]:
    # 保障按日期升序
    try:
        return sorted(points, key=lambda p: p.get("date", ""))
    except Exception:
        return points

def apply_window(points: List[Dict], window: Optional[int]) -> List[Dict]:
    """Return points filtered to the last `window` days based on the last point's date.
    Robust to malformed items; falls back to tail slicing on error.
    If window is falsy or <=0, returns the original list.
    """
    if not points or not window or window <= 0:
        return points
    pts = _sort_points(points)
    try:
        last_day = date.fromisoformat(pts[-1]["date"])  # may raise
        start = last_day - timedelta(days=window - 1)
        res = [p for p in pts if "date" in p and date.fromisoformat(p["date"]) >= start]
        # Defensive cap: if override file wasn't trimmed, keep only tail window items
        if len(res) > window * 2:
            res = res[-window:]
        return res
    except Exception:
        return pts[-window:]

def load_trend_override(port: str, window: Optional[int] = None) -> Optional[Dict]:
    """
    读取 overrides/{PORT}/trend.json 并按 window(天)过滤。
    返回形如：{"unlocode": "USLAX", "points": [...]} 或 None
    """
    path = DATA_DIR / port.upper() / "trend.json"
    obj = _safe_load_json(path)
    if not obj:
        return None

    pts: List[Dict] = obj.get("points", []) or []
    pts = _sort_points(pts)

    pts = apply_window(pts, window)

    return {"unlocode": port.upper(), "points": pts}

def enforce_window(payload: Dict, window: Optional[int]) -> Dict:
    """Ensure `payload["points"]` respects `window`. Modifies and returns the same dict."""
    pts = payload.get("points", []) or []
    pts = apply_window(pts, window)
    payload["points"] = pts
    return payload

def latest_from_points(points: List[Dict]) -> Optional[Dict]:
    return points[-1] if points else None

def snapshot_from_override(port: str) -> Optional[Dict]:
    """
    基于覆盖文件的最后一点拼快照（供 ports.py 使用）。
    """
    ov = load_trend_override(port)
    if not ov or not ov["points"]:
        return None
    last = latest_from_points(ov["points"])
    # allow embedded as_of; else build midnight-as_of from date
    as_of_date = last.get("date")
    as_of = last.get("as_of") or (as_of_date + "T00:00:00Z" if as_of_date else None)
    return {
        "unlocode": port.upper(),
        "as_of": as_of,
        "as_of_date": as_of_date,
        "metrics": {
            "vessels": last.get("vessels"),
            "avg_wait_hours": last.get("avg_wait_hours"),
            "congestion_score": last.get("congestion_score"),
        },
        "source": {"src": "override"},
    }