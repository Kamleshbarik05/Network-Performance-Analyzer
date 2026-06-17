# backend/app/services/bandwidth.py

import time
import psutil
from typing import Dict, List, Tuple

def get_bandwidth_usage(interval: float = 1.0) -> Tuple[Dict[str, float], List[Dict]]:
    """
    Measures current download and upload speeds (in KB/s) across interfaces,
    along with error and drop stats for each active network interface card (NIC).
    Returns: (global_rates, list_of_interface_details)
    """
    # 1. Take initial snapshot of IO counters for all interfaces
    io1 = psutil.net_io_counters(pernic=True)
    time.sleep(interval)
    # 2. Take second snapshot after the interval
    io2 = psutil.net_io_counters(pernic=True)

    interfaces_data = []
    total_download_bytes = 0.0
    total_upload_bytes = 0.0

    for name in io1.keys():
        if name not in io2:
            continue

        nic1 = io1[name]
        nic2 = io2[name]

        # Calculate difference (in bytes)
        bytes_sent = nic2.bytes_sent - nic1.bytes_sent
        bytes_recv = nic2.bytes_recv - nic1.bytes_recv

        # Calculate rate (KB/s) based on interval
        upload_rate = (bytes_sent / 1024.0) / interval
        download_rate = (bytes_recv / 1024.0) / interval

        # Only track active interfaces to avoid cluttering (devices showing traffic)
        # We also include loopback (lo/Ethernet/Wi-Fi) if it has sent/received anything
        if nic2.bytes_sent > 0 or nic2.bytes_recv > 0:
            interfaces_data.append({
                "name": name,
                "bytes_sent": nic2.bytes_sent,
                "bytes_recv": nic2.bytes_recv,
                "packets_sent": nic2.packets_sent,
                "packets_recv": nic2.packets_recv,
                "errin": nic2.errin,
                "errout": nic2.errout,
                "dropin": nic2.dropin,
                "dropout": nic2.dropout,
                "download_kbps": round(download_rate * 8.0, 2), # Convert KB/s to kbps
                "upload_kbps": round(upload_rate * 8.0, 2)
            })

            # Don't add loopback adapter to total internet bandwidth calculations
            if "loopback" not in name.lower() and "lo" != name.lower():
                total_download_bytes += bytes_recv
                total_upload_bytes += bytes_sent

    # Calculate global speeds in KB/s
    global_download_rate = (total_download_bytes / 1024.0) / interval
    global_upload_rate = (total_upload_bytes / 1024.0) / interval

    global_rates = {
        "download_kbps": round(global_download_rate * 8.0, 2), # kbps
        "upload_kbps": round(global_upload_rate * 8.0, 2)
    }

    return global_rates, interfaces_data