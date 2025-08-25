from typing import List, Optional
from datetime import date, datetime, timezone
from pydantic import BaseModel, Field

class TrendPoint(BaseModel):
    date: date
    vessels: Optional[int] = None
    avg_wait_hours: Optional[float] = None
    congestion_score: Optional[float] = None
    src: Optional[str] = None

class TrendResponse(BaseModel):
    unlocode: str
    points: List[TrendPoint] = Field(default_factory=list)

class DwellPoint(BaseModel):
    date: date
    dwell_hours: Optional[float] = None
    src: Optional[str] = None

class DwellResponse(BaseModel):
    unlocode: str
    points: List[DwellPoint] = Field(default_factory=list)

class SnapshotMetrics(BaseModel):
    vessels: Optional[int] = None
    avg_wait_hours: Optional[float] = None
    congestion_score: Optional[float] = None

class SourceInfo(BaseModel):
    src: Optional[str] = None
    src_loaded_at: Optional[datetime] = None

class SnapshotResponse(BaseModel):
    unlocode: str
    as_of: datetime
    metrics: SnapshotMetrics
    source: Optional[SourceInfo] = None
