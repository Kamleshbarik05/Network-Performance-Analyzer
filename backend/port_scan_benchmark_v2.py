# port_scan_benchmark_v2.py
#
# Improved version: runs the scan across a LARGER port range, repeats it
# multiple times, and reports the median -- this avoids the "suspiciously
# precise decimal from a tiny sample" problem (e.g. 97.5 ports/sec from a
# ~0.4s run looks unreliable; a 5000-port scan averaged over 3 runs does not).
#
# HOW TO USE:
#   1. Import your actual scan function where marked >>> ADAPT
#   2. Run: python port_scan_benchmark_v2.py
#   3. Use the MEDIAN throughput as your resume number -- it's the most
#      defensible because it's reproducible and not a one-off lucky/unlucky run.

import asyncio
import time
import statistics

from app.services.scanner import scan_target_ports

PORT_RANGE = (1, 5000)   # scan a realistic, larger range than before
NUM_RUNS = 5              # repeat the scan multiple times for a stable median
TARGET_HOST = "127.0.0.1"


async def run_single_scan():
    start = time.perf_counter()

    ports_list = list(range(PORT_RANGE[0], PORT_RANGE[1] + 1))
    results = await scan_target_ports(TARGET_HOST, ports=ports_list)

    elapsed = time.perf_counter() - start
    ports_scanned = PORT_RANGE[1] - PORT_RANGE[0] + 1
    rate = ports_scanned / elapsed
    return elapsed, ports_scanned, rate


async def main():
    print("==================================================")
    print(f" Port Scan Benchmark -- {PORT_RANGE[0]}-{PORT_RANGE[1]} "
          f"({PORT_RANGE[1]-PORT_RANGE[0]+1} ports), {NUM_RUNS} runs")
    print("==================================================")

    rates = []
    for i in range(NUM_RUNS):
        elapsed, ports_scanned, rate = await run_single_scan()
        rates.append(rate)
        print(f"  Run {i+1}: {ports_scanned} ports in {elapsed:.2f}s -> {rate:.1f} ports/sec")

    median_rate = statistics.median(rates)
    mean_rate = statistics.mean(rates)
    stdev = statistics.stdev(rates) if len(rates) > 1 else 0.0

    print("\n--- Summary ---")
    print(f"  Median throughput: {median_rate:.1f} ports/sec  <-- use this on the resume")
    print(f"  Mean throughput:   {mean_rate:.1f} ports/sec")
    print(f"  Std deviation:     {stdev:.1f}")


if __name__ == "__main__":
    asyncio.run(main())