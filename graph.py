

import matplotlib.pyplot as plt
import time

def real_time_latency_graph(get_latency_function):

    latency_values = []

    plt.ion()   # interactive mode

    for i in range(10):

        latency = get_latency_function()

        if latency:
            latency_values.append(latency)

        plt.clf()

        x = list(range(1, len(latency_values)+1))

        plt.plot(x, latency_values, marker="o")

        plt.title("Real-Time Network Latency Monitoring")

        plt.xlabel("Test Number")

        plt.ylabel("Latency (ms)")

        plt.grid(True)

        plt.pause(1)

        time.sleep(1)

    plt.ioff()
    plt.show()