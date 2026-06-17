# backend/app/services/speedtest.py

import asyncio
import speedtest
from typing import Dict

def run_speedtest_sync() -> Dict[str, float]:
    """
    Synchronous blocking function that connects to Speedtest.net,
    finds the optimal server, and measures download/upload speeds.
    """
    print("[SPEEDTEST] Initiating test on Speedtest.net servers...")
    # Initialize the Speedtest client
    st = speedtest.Speedtest(secure=True)
    
    # 1. Find the best server based on latency
    st.get_best_server()
    
    # 2. Run download test (returns bytes/sec, convert to Mbps)
    download_bps = st.download()
    download_mbps = download_bps / 10**6
    
    # 3. Run upload test (convert to Mbps)
    upload_bps = st.upload()
    upload_mbps = upload_bps / 10**6
    
    # 4. Get ping latency to the speedtest server
    ping_ms = st.results.ping
    
    print(f"[SPEEDTEST] Completed. Down: {round(download_mbps, 2)} Mbps, Up: {round(upload_mbps, 2)} Mbps")
    return {
        "download_mbps": round(download_mbps, 2),
        "upload_mbps": round(upload_mbps, 2),
        "ping_ms": round(ping_ms, 2)
    }

async def run_speedtest_async() -> Dict[str, float]:
    """
    Asynchronous wrapper. Offloads the heavy blocking speedtest
    calculation to a separate thread in the background, keeping
    the FastAPI event loop fully responsive.
    """
    # asyncio.to_thread runs the synchronous function in a separate thread pool
    return await asyncio.to_thread(run_speedtest_sync)