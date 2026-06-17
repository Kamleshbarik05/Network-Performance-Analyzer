# backend/app/schemas.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict

# --- Latency Telemetry ---
class LatencyBase(BaseModel):
    host: str
    latency_ms: Optional[float]
    jitter_ms: Optional[float]
    packet_loss_pct: float

class LatencyCreate(LatencyBase):
    pass

class LatencyResponse(LatencyBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- Speed Test Result ---
class SpeedTestBase(BaseModel):
    download_mbps: float
    upload_mbps: float
    ping_ms: float

class SpeedTestCreate(SpeedTestBase):
    pass

class SpeedTestResponse(SpeedTestBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- System Alerts ---
class AlertBase(BaseModel):
    alert_type: str
    message: str
    severity: str
    is_resolved: bool

class AlertCreate(AlertBase):
    pass

class AlertResponse(AlertBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- Real-Time Telemetry Streaming Schema ---
class BandwidthUsage(BaseModel):
    download_kbps: float
    upload_kbps: float

class ActiveInterface(BaseModel):
    name: str
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

class TelemetryPayload(BaseModel):
    timestamp: str
    latency: Optional[float]
    jitter: Optional[float]
    packet_loss: float
    bandwidth: BandwidthUsage
    interfaces: List[ActiveInterface]
    active_alerts: List[AlertResponse]
