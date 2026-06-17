# backend/app/main.py

import os
import asyncio
from datetime import datetime
import json
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .database import engine, Base, get_db
from .models import HistoricalLatency, SystemAlert, SpeedTestResult
from .schemas import TelemetryPayload, AlertResponse, LatencyResponse, SpeedTestResponse
from .services.latency import ping_host
from .services.bandwidth import get_bandwidth_usage
from .services.scanner import scan_target_ports
from .services.sniffer import global_sniffer
from .services.speedtest import run_speedtest_async

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./network_analyzer.db")
PING_TARGET_HOST = os.getenv("PING_TARGET_HOST", "8.8.8.8")
LATENCY_WARNING_THRESHOLD = float(os.getenv("LATENCY_WARNING_THRESHOLD_MS", "120.0"))
PACKET_LOSS_CRITICAL_THRESHOLD = float(os.getenv("PACKET_LOSS_CRITICAL_THRESHOLD_PCT", "10.0"))

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enterprise Network Analyzer API")

# --- CORS & WebSocket Middleware Setup ---

# Define standard CORS parameters for HTTP endpoints
class CustomCORSMiddleware:
    def __init__(self, app):
        self.app = app
        self.cors = CORSMiddleware(
            app=app,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            # Bypass CORS check for WebSocket connections to prevent 403 Forbidden
            await self.app(scope, receive, send)
        else:
            # Apply standard CORS rules for HTTP requests (REST API endpoints)
            await self.cors(scope, receive, send)

# Register the custom CORS bypass middleware
app.add_middleware(CustomCORSMiddleware)

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload_str = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(payload_str)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
background_task = None

# --- Telemetry Background Loop ---
async def telemetry_background_loop():
    print("[BACKGROUND TASK] Telemetry loop started.")
    print(f"[BACKGROUND TASK] Target: {PING_TARGET_HOST}, Latency Alert Threshold: {LATENCY_WARNING_THRESHOLD}ms")
    
    while True:
        try:
            # 1. Latency & Jitter Check
            latency, jitter, packet_loss = ping_host(PING_TARGET_HOST, count=3)

            # 2. Bandwidth Traffic Check (1-second sampling)
            bandwidth, interfaces = get_bandwidth_usage(interval=1.0)

            # 3. Read Packet Sniffer Stats (Thread-safe snapshot)
            sniffer_stats = global_sniffer.get_statistics()

            # Open DB session
            from .database import SessionLocal
            db = SessionLocal()

            try:
                # Log ping details
                hist_log = HistoricalLatency(
                    host=PING_TARGET_HOST,
                    latency_ms=latency,
                    jitter_ms=jitter,
                    packet_loss_pct=packet_loss
                )
                db.add(hist_log)

                # Threshold checks for warnings
                active_alerts = []
                
                if latency and latency > LATENCY_WARNING_THRESHOLD:
                    alert_msg = f"High network latency: {latency} ms."
                    alert = SystemAlert(alert_type="latency", message=alert_msg, severity="WARNING")
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    active_alerts.append(alert)

                if packet_loss > PACKET_LOSS_CRITICAL_THRESHOLD:
                    alert_msg = f"Critical packet loss: {packet_loss}%."
                    alert = SystemAlert(alert_type="packet_loss", message=alert_msg, severity="CRITICAL")
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    active_alerts.append(alert)

                db.commit()

                # Format alerts
                alerts_payload = [
                    {
                        "id": a.id,
                        "timestamp": a.timestamp.isoformat(),
                        "alert_type": a.alert_type,
                        "message": a.message,
                        "severity": a.severity,
                        "is_resolved": a.is_resolved
                    } for a in active_alerts
                ]

                # 4. Consolidate into a single telemetry payload
                payload = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "latency": latency,
                    "jitter": jitter,
                    "packet_loss": packet_loss,
                    "bandwidth": bandwidth,
                    "interfaces": interfaces,
                    "active_alerts": alerts_payload,
                    "sniffer": sniffer_stats  # Streaming the live protocol packet counts
                }

                # 5. Broadcast payload to all WebSocket clients
                await manager.broadcast(payload)

            except Exception as db_err:
                print(f"[BACKGROUND TASK] DB Error: {db_err}")
                db.rollback()
            finally:
                db.close()

        except Exception as err:
            print(f"[BACKGROUND TASK] General Loop Error: {err}")

        # Poll every 2 seconds
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event():
    global background_task
    # Start the async telemetry loop
    background_task = asyncio.create_task(telemetry_background_loop())
    # Start the background Scapy packet sniffer thread
    global_sniffer.start()

@app.on_event("shutdown")
async def shutdown_event():
    global background_task
    if background_task:
        background_task.cancel()
    # Safely terminate the sniffer thread
    global_sniffer.stop()

# --- REST API Endpoints ---

@app.get("/api/history/latency", response_model=List[LatencyResponse])
def get_latency_history(limit: int = 50, db: Session = Depends(get_db)):
    """
    Returns latest ping latency logs for charts.
    """
    return db.query(HistoricalLatency).order_by(HistoricalLatency.timestamp.desc()).limit(limit).all()

@app.get("/api/alerts", response_model=List[AlertResponse])
def get_alerts(limit: int = 20, db: Session = Depends(get_db)):
    """
    Returns latest warning alerts.
    """
    return db.query(SystemAlert).order_by(SystemAlert.timestamp.desc()).limit(limit).all()

@app.post("/api/speedtest", response_model=SpeedTestResponse)
async def trigger_speedtest(db: Session = Depends(get_db)):
    """
    Triggers a thread-offloaded Speedtest.net speed test and logs results.
    """
    try:
        results = await run_speedtest_async()
        db_result = SpeedTestResult(
            download_mbps=results["download_mbps"],
            upload_mbps=results["upload_mbps"],
            ping_ms=results["ping_ms"]
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speed test failed: {str(e)}")

@app.get("/api/history/speedtest", response_model=List[SpeedTestResponse])
def get_speedtest_history(limit: int = 10, db: Session = Depends(get_db)):
    """
    Returns historical speed test data.
    """
    return db.query(SpeedTestResult).order_by(SpeedTestResult.timestamp.desc()).limit(limit).all()

@app.get("/api/scan")
async def run_port_scan(ip: str, ports: Optional[str] = Query(None)):
    """
    Runs an asynchronous concurrent port scanner on the target IP.
    """
    ports_list = None
    if ports:
        try:
            ports_list = [int(p.strip()) for p in ports.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Ports must be comma-separated integers.")
    
    results = await scan_target_ports(ip, ports_list)
    return results

@app.get("/api/sniffer/stats")
def get_sniffer_stats():
    """
    Returns a manual snapshot of the packet sniffer stats.
    """
    return global_sniffer.get_statistics()

# --- WebSocket Telemetry Endpoint ---
@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)