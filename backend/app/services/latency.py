# backend/app/services/latency.py

import time
import math
from typing import Dict, List, Optional, Tuple
from ping3 import ping

def calculate_jitter(latencies: List[float]) -> float:
    """
    Calculates jitter based on RFC 1889.
    Jitter is the average absolute difference between consecutive latency measurements.
    Formula: Sum(|Latency_i - Latency_{i-1}|) / (N - 1)
    """
    if len(latencies) < 2:
        return 0.0
    
    diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
    return sum(diffs) / len(diffs)

def ping_host(host: str = "8.8.8.8", count: int = 5) -> Tuple[Optional[float], Optional[float], float]:
    """
    Pings a host multiple times.
    Returns: (average_latency_ms, jitter_ms, packet_loss_percentage)
    """
    latencies = []
    lost_packets = 0

    for _ in range(count):
        try:
            # ping returns response time in seconds, or None if timed out / unreachable
            response_time = ping(host, timeout=1.0)
            if response_time is not None:
                # Convert seconds to milliseconds
                latencies.append(response_time * 1000)
            else:
                lost_packets += 1
        except Exception:
            lost_packets += 1
        time.sleep(0.1)  # small gap between pings

    packet_loss_pct = (lost_packets / count) * 100.0

    if not latencies:
        return None, None, packet_loss_pct

    avg_latency = sum(latencies) / len(latencies)
    jitter = calculate_jitter(latencies)

    return round(avg_latency, 2), round(jitter, 2), round(packet_loss_pct, 2)

def run_traceroute(host: str = "8.8.8.8", max_hops: int = 20) -> List[Dict]:
    """
    Performs a route diagnostic (traceroute) to see all hop routers.
    Returns a list of dictionaries with hop information.
    """
    hops = []
    
    for ttl in range(1, max_hops + 1):
        start_time = time.time()
        try:
            # ping3 can send raw packets with specified TTL (Time-To-Live).
            # When TTL expires, the router returns an ICMP Time Exceeded packet.
            # ping3 returns the IP address of the router that sent the TTL expiry.
            hop_ip = ping(host, ttl=ttl, timeout=1.5)
            rtt = (time.time() - start_time) * 1000
            
            if hop_ip is None:
                # Timed out hop (router hides ICMP messages)
                hops.append({"hop": ttl, "ip": "*", "rtt_ms": None})
            elif hop_ip is True or hop_ip == host:
                # Reached the final destination
                hops.append({"hop": ttl, "ip": host, "rtt_ms": round(rtt, 2)})
                break
            else:
                # Found intermediate router
                hops.append({"hop": ttl, "ip": str(hop_ip), "rtt_ms": round(rtt, 2)})
        except Exception as e:
            hops.append({"hop": ttl, "ip": "Error", "rtt_ms": None})
            
    return hops
