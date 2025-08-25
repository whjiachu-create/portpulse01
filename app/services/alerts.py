from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Tuple

# 轻量工具：分位数、MAD、变点分数
def _quantile(xs: List[float], q: float) -> float:
    if not xs: return float("nan")
    xs = sorted(xs); n = len(xs); p = (n-1)*q
    i, f = int(p), p-int(p)
    return xs[i] if f==0 else xs[i]*(1-f)+xs[min(i+1,n-1)]*f

def _mad(xs: List[float]) -> float:
    if not xs: return 0.0
    med = _quantile(xs, 0.5)
    dev = [abs(x-med) for x in xs]
    return _quantile(dev, 0.5) or 1e-9

def _change_score(recent: List[float], prev: List[float]) -> float:
    """简易变点：最近k均值 vs 前k均值，用 MAD 归一"""
    if not recent or not prev: return 0.0
    mu_r, mu_p = sum(recent)/len(recent), sum(prev)/len(prev)
    s = abs(mu_r-mu_p) / _mad(prev)
    return s

@dataclass
class SeriesPoint:
    d: date
    v: Optional[float]  # 允许空洞（None）

@dataclass
class Alert:
    date: date
    metric: str
    delta: float
    severity: str
    explain: str

def compute_alerts(points: List[SeriesPoint],
                   metric_name: str="dwell_hours",
                   min_points: int=8) -> List[Alert]:
    """分位阈值 + 简单变点。返回 0或1 条 alert。"""
    xs = [p.v for p in points if p.v is not None]
    if len(xs) < min_points:
        return []

    latest = xs[-1]
    # 基线 = 前半段的中位数；阈值使用 IQR（Q75-Q25）
    first_half = xs[:len(xs)//2]
    med = _quantile(first_half, 0.5)
    q25 = _quantile(first_half, 0.25)
    q75 = _quantile(first_half, 0.75)
    iqr = max(q75 - q25, 1e-9)

    delta = float(round(latest - med, 2))
    # 变点分数（最近k=3 vs 前k=3）
    k = min(3, len(xs)//4 or 1)
    cp = _change_score(xs[-k:], xs[-2*k:-k] if len(xs) >= 2*k else xs[:-k])

    # 规则融合：按照 |delta| 与 cp 两者取重
    # 等级：high(>=1.5*IQR 或 cp>=6) / medium(>=0.75*IQR 或 cp>=3) / low(其他非零)
    ad = abs(delta)
    if ad >= 1.5*iqr or cp >= 6:
        sev = "high"
    elif ad >= 0.75*iqr or cp >= 3:
        sev = "medium"
    elif ad > 0:
        sev = "low"
    else:
        return []

    msg = f"Δ vs baseline={med:.1f}h; IQR={iqr:.1f}h; cp={cp:.1f}"
    return [Alert(date=points[-1].d, metric=metric_name, delta=delta, severity=sev, explain=msg)]
