# backend/app/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from .database import Base

class HistoricalLatency(Base):
    __tablename__ = "historical_latency"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    host = Column(String, index=True)
    latency_ms = Column(Float, nullable=True)
    jitter_ms = Column(Float, nullable=True)
    packet_loss_pct = Column(Float, default=0.0)

class SpeedTestResult(Base):
    __tablename__ = "speed_test_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    download_mbps = Column(Float)
    upload_mbps = Column(Float)
    ping_ms = Column(Float)

class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    alert_type = Column(String, index=True)  # e.g., "latency", "packet_loss", "interface_error"
    message = Column(String)
    severity = Column(String)  # "WARNING", "CRITICAL"
    is_resolved = Column(Boolean, default=False)
