
# This file checks network latency using ping

from ping3 import ping

def check_latency():

    host = "8.8.8.8"   # Google DNS server

    print("\nChecking Network Latency...")

    response = ping(host)

    if response:
        latency = response * 1000
        print("Latency:", round(latency, 2), "ms")
        return latency
    else:
        print("Network unreachable")
        return None