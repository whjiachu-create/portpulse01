# app/services/alerts.py
from __future__ import annotations
from statistics import median
from typing import List, Dict

def _quantiles(xs: List[float], qs=(0.1, 0.5, 0.9)) -> Dict[float, float]:
    if not xs:
        return {}
    ys = sorted(xs)
    n = len(ys)
    out = {}
    for q in qs:
        i = q*(n-1)
        lo, hi = int(i), min(int(i)+1, n-1)
        w = i - lo
        out[q] = ys[lo]*(1-w) + ys[hi]*w
    return out

def compute_dwell_alert(points: List[Dict]) -> List[Dict]:
    """
    points: [{"date": "YYYY-MM-DD", "dwell_hours": float, "src": "..."} ...] 按日期升序
    """
    if len(points) < 7:
        return []

    vals = [float(p["dwell_hours"]) for p in points]
    latest = vals[-1]
    qs = _quantiles(vals[:-1], qs=(0.1, 0.5, 0.9))
    p10, p50, p90 = qs.get(0.1), qs.get(0.5), qs.get(0.9)

    # 变点：最近3天均值 vs 之前7天均值
    tail3 = median(vals[-3:]) if len(vals) >= 3 else latest
    head7 = median(vals[:-3][-7:]) if len(vals) > 10 else median(vals[:-1])

    delta = latest - p50
    norm = 0.0
    band = max(p90 - p50, p50 - p10, 1e-6)
    norm = delta / band  # 归一化偏离

    severity = "low"
    if abs(norm) >= 1.5:
        severity = "medium"
    if abs(norm) >= 2.5:
        severity = "high"

    why = []
    if latest >= p90:
        why.append("latest ≥ p90（显著偏高）")
    elif latest <= p10:
        why.append("latest ≤ p10（显著偏低）")

    if abs(tail3 - head7) >= max(0.2 * max(p50, 1.0), 0.5):  # 相对或绝对阈
        why.append("近3天均值相对近段基线有显著变化（变点）")

    return [{
        "type": "dwell_change",
        "latest": round(latest, 2),
        "median": round(p50, 2),
        "p10": round(p10, 2),
        "p90": round(p90, 2),
        "change_vs_median": round(delta, 2),
        "severity": severity,
        "why": "; ".join(why) if why else "波动在正常范围"
    }]