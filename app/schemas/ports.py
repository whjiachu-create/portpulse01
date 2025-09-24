from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

class PortOverview(BaseModel):
    unlocode: str = Field(..., description="联合国港口代码，5 位")
    port_name: Optional[str] = Field(None, description="港口名称")
    country: Optional[str] = Field(None, description="国家/地区")
    arrivals_7d: Optional[int] = Field(None, ge=0)
    departures_7d: Optional[int] = Field(None, ge=0)
    waiting_vessels: Optional[int] = Field(None, ge=0)
    avg_wait_hours: Optional[float] = Field(None, ge=0)
    avg_berth_hours: Optional[float] = Field(None, ge=0)
    updated_at: Optional[datetime] = Field(None)

class PortCallExpanded(BaseModel):
    call_id: str
    unlocode: str
    vessel_name: Optional[str] = None
    imo: Optional[int] = None
    mmsi: Optional[str] = None
    status: Optional[Literal["expected", "arrived", "anchorage", "berthed", "sailed"]] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    ata: Optional[datetime] = None
    atb: Optional[datetime] = None
    atd: Optional[datetime] = None
    berth: Optional[str] = None
    terminal: Optional[str] = None
    last_updated_at: Optional[datetime] = None

class PortCallProcessed(BaseModel):
    call_id: str
    unlocode: str
    phase: Optional[Literal["waiting", "berthing", "turnaround"]] = None
    wait_hours: Optional[float] = Field(None, ge=0)
    service_time_hours: Optional[float] = Field(None, ge=0)
    turnaround_hours: Optional[float] = Field(None, ge=0)
    updated_at: Optional[datetime] = None
