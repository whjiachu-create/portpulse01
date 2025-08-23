from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class PortOverview(BaseModel):
    """端口概览（用于 /v1/ports/{unlocode}/overview 的 JSON 结构）"""
    unlocode: str = Field(..., description="联合国港口代码，5 位")
    port_name: Optional[str] = Field(None, description="港口名称")
    country: Optional[str] = Field(None, description="国家/地区")
    arrivals_7d: Optional[int] = Field(None, ge=0, description="近 7 日到港数")
    departures_7d: Optional[int] = Field(None, ge=0, description="近 7 日离港数")
    waiting_vessels: Optional[int] = Field(None, ge=0, description="当前锚地等待船舶数")
    avg_wait_hours: Optional[float] = Field(None, ge=0, description="平均等待时长（小时）")
    avg_berth_hours: Optional[float] = Field(None, ge=0, description="平均靠泊时长（小时）")
    updated_at: Optional[datetime] = Field(None, description="数据快照时间戳")


class PortCallExpanded(BaseModel):
    """单船靠港过程的扩展信息（明细视图）"""
    call_id: str = Field(..., description="靠港记录 ID")
    unlocode: str = Field(..., description="港口 UN/LOCODE")
    vessel_name: Optional[str] = Field(None, description="船名")
    imo: Optional[int] = Field(None, description="IMO 号")
    mmsi: Optional[str] = Field(None, description="MMSI")
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
    """经过加工处理后的指标（便于分析/看板）"""
    call_id: str
    unlocode: str
    phase: Optional[Literal["waiting", "berthing", "turnaround"]] = None
    wait_hours: Optional[float] = Field(None, ge=0)
    service_time_hours: Optional[float] = Field(None, ge=0, description="作业时长（小时）")
    turnaround_hours: Optional[float] = Field(None, ge=0, description="到港到离港总周期（小时）")
    updated_at: Optional[datetime] = None