# backend/telemetry_benchmark.py

import os
import sys
import asyncio
import time
import json
from datetime import datetime

# Add the current folder to sys.path so we can import the 'app' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import HistoricalLatency
from app.services.scanner import scan_target_ports

try:
    import websockets
except ImportError:
    print("[ERROR] Please install websockets library: pip install websockets")
    sys.exit(1)

# --- 1. Port Scanner Benchmark ---
async def benchmark_port_scanner():
    print("\n==================================================")
    print("        BENCHMARK 1: ASYNC PORT SCANNER")
    print("==================================================")
    
    target_ip = "127.0.0.1"
    ports_to_scan = list(range(1, 1001)) # Scan ports 1 to 1000
    
    print(f"Starting async port scan on {target_ip} for {len(ports_to_scan)} ports...")
    
    start_time = time.time()
    results = await scan_target_ports(target_ip, ports=ports_to_scan, max_concurrency=100)
    duration = time.time() - start_time
    
    open_ports = [r for r in results if r["status"] == "Open"]
    scan_rate = len(ports_to_scan) / duration
    
    print(f"Completed in: {duration:.4f} seconds")
    print(f"Open Ports Found: {len(open_ports)} / {len(results)}")
    print(f"Scan Rate: {scan_rate:.2f} ports/second (at max 100 concurrency)")
    return {
        "duration_seconds": duration,
        "scan_rate": scan_rate,
        "open_ports_count": len(open_ports)
    }

# --- 2. WebSocket Telemetry Benchmark ---
async def benchmark_websocket():
    print("\n==================================================")
    print("        BENCHMARK 2: WEBSOCKET TELEMETRY")
    print("==================================================")
    
    uri = "ws://127.0.0.1:8000/ws/telemetry"
    print(f"Connecting to live WebSocket route: {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Successfully connected to WebSocket stream!")
            
            # Read 3 telemetry packets broadcasted by the backend
            packet_times = []
            for i in range(1, 4):
                start = time.time()
                message = await websocket.recv()
                rtt = (time.time() - start) * 1000
                packet_times.append(rtt)
                
                payload = json.loads(message)
                print(f"  Packet {i}: Received in {rtt:.2f}ms")
                print(f"    - Latency (Ping): {payload.get('latency')} ms")
                print(f"    - Jitter: {payload.get('jitter')} ms")
                print(f"    - Bandwidth: Dn={payload['bandwidth'].get('download_kbps')} kbps, Up={payload['bandwidth'].get('upload_kbps')} kbps")
                print(f"    - Sniffer Packet Count: {payload.get('sniffer', {}).get('total_packets')} packets")
            
            avg_recv_rtt = sum(packet_times) / len(packet_times)
            print(f"WebSocket diagnostics complete. Average frame receive RTT: {avg_recv_rtt:.2f}ms")
            return {"avg_rtt_ms": avg_recv_rtt}
            
    except Exception as e:
        print(f"[ERROR] WebSocket connection failed: {e}")
        print("Please ensure your FastAPI backend is running before starting the benchmark.")
        return None

# --- 3. Database Write Benchmark (SQLAlchemy & SQLite) ---
def benchmark_database_writes():
    print("\n==================================================")
    print("        BENCHMARK 3: DATABASE WRITE PERFORMANCE")
    print("==================================================")
    
    db = SessionLocal()
    num_records = 100
    print(f"Benchmarking {num_records} write insertions to SQLite...")
    
    # Clean up test rows afterwards
    test_hosts = []
    
    # Case A: Sequential Commits (Highly Inefficient)
    start_time = time.time()
    for i in range(num_records):
        log_entry = HistoricalLatency(
            host=f"test-seq-{i}.com",
            latency_ms=10.0 + i,
            jitter_ms=1.2,
            packet_loss_pct=0.0
        )
        db.add(log_entry)
        db.commit() # Commits each write to disk individually
        test_hosts.append(log_entry.host)
    duration_seq = time.time() - start_time
    avg_seq = (duration_seq / num_records) * 1000
    print(f"Sequential Commits: {duration_seq:.4f}s total ({avg_seq:.2f}ms per write transaction)")
    
    # Case B: Bulk Commit (Transactional Optimization)
    start_time = time.time()
    for i in range(num_records):
        log_entry = HistoricalLatency(
            host=f"test-bulk-{i}.com",
            latency_ms=10.0 + i,
            jitter_ms=1.2,
            packet_loss_pct=0.0
        )
        db.add(log_entry)
        test_hosts.append(log_entry.host)
    db.commit() # Commits all 100 writes in a single disk transaction
    duration_bulk = time.time() - start_time
    avg_bulk = (duration_bulk / num_records) * 1000
    print(f"Bulk Transaction Commit: {duration_bulk:.4f}s total ({avg_bulk:.2f}ms per write transaction)")
    
    # Clean up benchmarks entries to avoid SQLite bloat
    print("Cleaning benchmark test entries...")
    db.query(HistoricalLatency).filter(HistoricalLatency.host.in_(test_hosts)).delete(synchronize_session=False)
    db.commit()
    db.close()
    
    speed_increase = (duration_seq / duration_bulk) if duration_bulk > 0 else 1
    print(f"Optimization Impact: Bulk writes are {speed_increase:.1f}x faster than sequential commits!")
    return {
        "sequential_ms_per_write": avg_seq,
        "bulk_ms_per_write": avg_bulk,
        "speed_increase_multiplier": speed_increase
    }

# --- Main Driver ---
async def main():
    print("==================================================")
    print("   TELEMETRY & SYSTEMS PERFORMANCE BENCHMARK")
    print("==================================================")
    
    # 1. Run database writes
    db_results = benchmark_database_writes()
    
    # 2. Run async port scanner
    scanner_results = await benchmark_port_scanner()
    
    # 3. Run websocket telemetry check
    ws_results = await benchmark_websocket()
    
    print("\n==================================================")
    print("             BENCHMARK SUMMARY")
    print("==================================================")
    print(f"Port Scan Rate: {scanner_results['scan_rate']:.2f} ports/sec")
    print(f"SQLite Seq Write: {db_results['sequential_ms_per_write']:.2f} ms/record")
    print(f"SQLite Bulk Write: {db_results['bulk_ms_per_write']:.2f} ms/record ({db_results['speed_increase_multiplier']:.1f}x speed improvement)")
    if ws_results:
        print(f"WebSocket Receive Latency: {ws_results['avg_rtt_ms']:.2f} ms")
    else:
        print("WebSocket Telemetry: FAILED (Backend was offline)")

if __name__ == "__main__":
    asyncio.run(main())