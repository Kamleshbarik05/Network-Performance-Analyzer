
# This file monitors network bandwidth usage

import psutil
import time

def check_bandwidth():

    print("\nChecking Bandwidth Usage...")

    net1 = psutil.net_io_counters()

    time.sleep(1)

    net2 = psutil.net_io_counters()

    download = (net2.bytes_recv - net1.bytes_recv) / 1024
    upload = (net2.bytes_sent - net1.bytes_sent) / 1024

    print("Download Usage:", round(download,2), "KB/s")
    print("Upload Usage:", round(upload,2), "KB/s")