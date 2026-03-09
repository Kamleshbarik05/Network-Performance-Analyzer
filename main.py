# main.py

from latency import check_latency
from speed_test import check_speed
from bandwidth import check_bandwidth
from graph import real_time_latency_graph


print("\n=================================")
print("   NETWORK PERFORMANCE ANALYZER  ")
print("=================================")

# Run normal tests
check_latency()

check_speed()

check_bandwidth()

print("\nStarting real-time latency monitoring...\n")

# call graph
real_time_latency_graph(check_latency)

print("\nNetwork analysis completed!")