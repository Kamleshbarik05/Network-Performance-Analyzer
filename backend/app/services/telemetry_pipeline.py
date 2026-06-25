# backend/app/services/telemetry_pipeline.py

from abc import ABC, abstractmethod
from typing import Dict, List
import os
import psutil

class TelemetrySource(ABC):
    """
    Design Pattern: Strategy
    Abstract base class defining the interface for all telemetry collection strategies.
    """
    @abstractmethod
    def collect(self) -> Dict:
        pass

class TelemetryObserver(ABC):
    """
    Design Pattern: Observer
    Abstract base class defining the interface for objects observing telemetry updates.
    """
    @abstractmethod
    async def on_update(self, data: Dict) -> None:
        pass

class CPUTelemetry(TelemetrySource):
    """
    Design Pattern: Strategy
    Concrete strategy to collect CPU and Memory hardware metrics.
    """
    def collect(self) -> Dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent
        }

class NetworkTelemetry(TelemetrySource):
    """
    Design Pattern: Strategy
    Concrete strategy to collect ping round-trip times, packet loss, and interface bandwidth.
    """
    def collect(self) -> Dict:
        # Import inside method to avoid circular dependencies
        from .bandwidth import get_bandwidth_usage
        from .latency import ping_host
        
        target_host = os.getenv("PING_TARGET_HOST", "8.8.8.8")
        latency, jitter, packet_loss = ping_host(target_host, count=3)
        bandwidth, interfaces = get_bandwidth_usage(interval=1.0)
        
        return {
            "latency": latency,
            "jitter": jitter,
            "packet_loss": packet_loss,
            "bandwidth": bandwidth,
            "interfaces": interfaces
        }

class DiskTelemetry(TelemetrySource):
    """
    Design Pattern: Strategy
    Concrete strategy to collect system disk utilization.
    """
    def collect(self) -> Dict:
        try:
            disk = psutil.disk_usage('/')
            return {
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
        except Exception:
            return {
                "disk_percent": 0.0,
                "disk_free_gb": 0.0
            }

class TelemetryPipeline:
    """
    Design Pattern: Strategy
    Main orchestrator acting as the context for Strategy pattern and subject for Observer pattern.
    """
    def __init__(self, sources: List[TelemetrySource]):
        self.sources = sources
        self.observers: List[TelemetryObserver] = []

    def register_observer(self, observer: TelemetryObserver):
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer: TelemetryObserver):
        if observer in self.observers:
            self.observers.remove(observer)

    async def notify_observers(self, data: Dict):
        for observer in self.observers:
            await observer.on_update(data)

    def collect(self) -> Dict:
        merged = {}
        for source in self.sources:
            try:
                merged.update(source.collect())
            except Exception as e:
                print(f"[Strategy Error] Failed collecting from {source.__class__.__name__}: {e}")
        return merged

class WebSocketBroadcaster(TelemetryObserver):
    """
    Design Pattern: Observer
    Concrete observer that broadcasts new telemetry data frames to all active WebSocket connections.
    """
    def __init__(self, manager):
        self.manager = manager

    async def on_update(self, data: Dict) -> None:
        await self.manager.broadcast(data)