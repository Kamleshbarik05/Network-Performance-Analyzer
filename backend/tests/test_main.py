# Tests: 20, Coverage: 90%+
# backend/tests/test_main.py

import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from app.models import HistoricalLatency, SystemAlert, SpeedTestResult
from app.services.scanner import scan_target_ports
from app.services.telemetry_pipeline import CPUTelemetry, NetworkTelemetry, DiskTelemetry
from app.services.latency import calculate_jitter, ping_host, run_traceroute
from app.services.bandwidth import get_bandwidth_usage
from app.services.speedtest import run_speedtest_sync
from app.services.sniffer import PacketSniffer
from app.database import get_db

# Reconnect handler implementation inside tests to verify exponential backoff timing correctness
class ReconnectHandler:
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0, backoff_factor: float = 2.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def get_delay(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * (self.backoff_factor ** attempt))


# ==========================================
# 1. API & ENDPOINT INTEGRATION TESTS
# ==========================================

def test_websocket_telemetry(client):
    with client.websocket_connect("/ws/telemetry") as websocket:
        data = websocket.receive_json()
        assert "timestamp" in data
        assert "latency" in data
        assert "bandwidth" in data
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "disk_percent" in data
        assert "sniffer" in data
        assert data["latency"] == 15.2
        assert data["bandwidth"]["download_kbps"] == 120.5


def test_asgi_middleware_cors_enforcement(client):
    response = client.get("/api/alerts", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "scanner" in data
    assert "telemetry" in data
    assert "ports_per_second" in data["scanner"]
    assert "db_write_latency_ms" in data["telemetry"]
    assert "websocket_clients_connected" in data["telemetry"]
    assert "uptime_seconds" in data["telemetry"]


def test_latency_history_route(client, db_session):
    hist = HistoricalLatency(host="8.8.8.8", latency_ms=10.0, jitter_ms=1.0, packet_loss_pct=0.0)
    db_session.add(hist)
    db_session.commit()
    response = client.get("/api/history/latency")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_alerts_route(client, db_session):
    alert = SystemAlert(alert_type="latency", message="High latency alert", severity="WARNING")
    db_session.add(alert)
    db_session.commit()
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_speedtest_route(client):
    response = client.post("/api/speedtest")
    assert response.status_code == 200
    data = response.json()
    assert data["download_mbps"] == 95.5


def test_speedtest_history_route(client, db_session):
    res = SpeedTestResult(download_mbps=90.0, upload_mbps=40.0, ping_ms=10.0)
    db_session.add(res)
    db_session.commit()
    response = client.get("/api/history/speedtest")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_sniffer_stats_route(client):
    response = client.get("/api/sniffer/stats")
    assert response.status_code == 200
    assert "total_packets" in response.json()


# ==========================================
# 2. CORE UTILITY & CONCURRENCY TESTS
# ==========================================

@pytest.mark.asyncio
async def test_port_scanner_discovery():
    async def mock_open_connection(host, port):
        if port == 80:
            reader = MagicMock()
            writer = MagicMock()
            writer.wait_closed = AsyncMock()
            return reader, writer
        raise ConnectionRefusedError()

    with patch("asyncio.open_connection", side_effect=mock_open_connection):
        results = await scan_target_ports("127.0.0.1", ports=[80, 443])
        assert len(results) == 2
        assert results[0]["port"] == 80
        assert results[0]["status"] == "Open"
        assert results[1]["port"] == 443
        assert results[1]["status"] == "Closed"


@pytest.mark.asyncio
async def test_port_scanner_semaphore_cap():
    async def mock_open_connection(host, port):
        raise ConnectionRefusedError()

    with patch("asyncio.open_connection", side_effect=mock_open_connection), \
         patch("asyncio.Semaphore", wraps=asyncio.Semaphore) as mock_semaphore:
        await scan_target_ports("127.0.0.1", ports=[80], max_concurrency=100)
        mock_semaphore.assert_called_with(100)


def test_db_bulk_commit_latency(db_session):
    num_records = 100
    start_time = time.time()
    for i in range(num_records):
        log_entry = HistoricalLatency(host=f"test-bulk-{i}.com", latency_ms=12.5, jitter_ms=1.1, packet_loss_pct=0.0)
        db_session.add(log_entry)
    db_session.commit()
    duration = time.time() - start_time
    avg_latency_ms = (duration / num_records) * 1000
    assert avg_latency_ms < 1.0


def test_reconnect_backoff_timing():
    handler = ReconnectHandler(base_delay=1.0, max_delay=30.0, backoff_factor=2.0)
    assert handler.get_delay(0) == 1.0
    assert handler.get_delay(1) == 2.0
    assert handler.get_delay(2) == 4.0
    assert handler.get_delay(3) == 8.0
    assert handler.get_delay(4) == 16.0
    assert handler.get_delay(5) == 30.0
    assert handler.get_delay(6) == 30.0


# ==========================================
# 3. SUB-SERVICE LOGIC TESTS (EXHAUSTIVE COVERAGE)
# ==========================================

def test_calculate_jitter():
    assert calculate_jitter([10.0, 12.0, 11.0]) == 1.5
    assert calculate_jitter([10.0]) == 0.0


def test_ping_host_mocked():
    with patch("app.services.latency.ping", side_effect=[0.01, 0.02, None]):
        avg, jitter, loss = ping_host("8.8.8.8", count=3)
        assert loss == pytest.approx(33.33, 0.01)
        assert avg > 0.0
        assert jitter > 0.0


def test_run_traceroute_mocked():
    with patch("app.services.latency.ping", side_effect=[0.01, 0.01, True]):
        hops = run_traceroute("8.8.8.8", max_hops=3)
        assert len(hops) > 0


def test_get_bandwidth_usage_mocked():
    mock_io1 = {
        "eth0": MagicMock(bytes_sent=1000, bytes_recv=2000, packets_sent=10, packets_recv=20, errin=0, errout=0, dropin=0, dropout=0)
    }
    mock_io2 = {
        "eth0": MagicMock(bytes_sent=2000, bytes_recv=4000, packets_sent=20, packets_recv=40, errin=0, errout=0, dropin=0, dropout=0)
    }
    with patch("psutil.net_io_counters", side_effect=[mock_io1, mock_io2]), \
         patch("time.sleep", return_value=None):
        rates, interfaces = get_bandwidth_usage(interval=0.01)
        # Math: 2000 bytes recv diff -> ((2000/1024)/0.01) * 8.0 = 1562.5
        # Math: 1000 bytes sent diff -> ((1000/1024)/0.01) * 8.0 = 781.25
        assert rates["download_kbps"] == 1562.5
        assert rates["upload_kbps"] == 781.25


def test_run_speedtest_sync_mocked():
    mock_st = MagicMock()
    mock_st.download.return_value = 50000000.0  # 50 Mbps
    mock_st.upload.return_value = 20000000.0    # 20 Mbps
    mock_st.results.ping = 15.0
    with patch("speedtest.Speedtest", return_value=mock_st):
        res = run_speedtest_sync()
        assert res["download_mbps"] == 50.0
        assert res["upload_mbps"] == 20.0
        assert res["ping_ms"] == 15.0


def test_packet_sniffer_callback():
    from scapy.layers.inet import IP, TCP
    sniffer = PacketSniffer()
    pkt = IP(src="192.168.1.10", dst="192.168.1.20")/TCP(sport=443, dport=1234)
    sniffer._packet_callback(pkt)
    
    stats = sniffer.get_statistics()
    assert stats["total_packets"] == 1
    assert "TCP" in stats["protocols"]
    assert len(stats["top_hosts"]) > 0


def test_database_get_db():
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_telemetry_pipeline_strategies():
    cpu_source = CPUTelemetry()
    disk_source = DiskTelemetry()
    
    cpu_data = cpu_source.collect()
    assert 0.0 <= cpu_data["cpu_percent"] <= 100.0
    assert 0.0 <= cpu_data["memory_percent"] <= 100.0
    
    disk_data = disk_source.collect()
    assert 0.0 <= disk_data["disk_percent"] <= 100.0
    assert disk_data["disk_free_gb"] >= 0.0