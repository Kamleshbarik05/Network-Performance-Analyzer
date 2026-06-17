# backend/app/services/scanner.py

import asyncio
import time
from typing import List, Dict

# Standard common ports mapped to their default service names
COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    1433: "MSSQL",
    3306: "MySQL",
    3389: "RDP",
    8080: "HTTP-ALT"
}

async def scan_single_port(ip: str, port: int, semaphore: asyncio.Semaphore, timeout: float = 1.0) -> Dict:
    """
    Attempts to connect to a single TCP port asynchronously.
    Uses a semaphore to cap concurrent socket creation.
    """
    async with semaphore:
        start_time = time.time()
        try:
            # 1. Establish an asynchronous TCP connection
            connect_coro = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
            
            # 2. If it connects, port is OPEN. Measure Round Trip Time (RTT).
            rtt = (time.time() - start_time) * 1000
            
            # 3. Clean up the socket connection
            writer.close()
            await writer.wait_closed()
            
            return {
                "port": port,
                "service": COMMON_PORTS.get(port, "Unknown"),
                "status": "Open",
                "rtt_ms": round(rtt, 2)
            }
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            # If connection times out or is refused, the port is closed/filtered.
            return {
                "port": port,
                "service": COMMON_PORTS.get(port, "Unknown"),
                "status": "Closed",
                "rtt_ms": None
            }

async def scan_target_ports(ip: str, ports: List[int] = None, max_concurrency: int = 100) -> List[Dict]:
    """
    Scans a set of TCP ports on the target IP concurrently.
    """
    if not ports:
        ports = list(COMMON_PORTS.keys())

    # Limit active concurrent tasks to avoid exhausting OS sockets/file descriptors
    semaphore = asyncio.Semaphore(max_concurrency)
    
    # Create an async task for each port
    tasks = [scan_single_port(ip, port, semaphore) for port in ports]
    
    # Execute all port scans concurrently
    results = await asyncio.gather(*tasks)
    
    # Return results sorted by port number
    return sorted(results, key=lambda x: x["port"])