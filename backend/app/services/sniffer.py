# backend/app/services/sniffer.py

import threading
from collections import defaultdict
from typing import Dict, List
from scapy.all import sniff, IP, TCP, UDP, ICMP, ARP, DNS

class PacketSniffer:
    """
    A thread-safe packet sniffer that runs in a background thread,
    captures real-time network traffic, and compiles protocol/IP statistics.
    """
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Metrics storage
        self.total_packets = 0
        self.total_bytes = 0
        self.protocol_counts = defaultdict(int)
        self.protocol_bytes = defaultdict(int)
        self.top_ips = defaultdict(int) # Maps IP address to bytes transferred

    def _packet_callback(self, packet):
        """
        Callback triggered by Scapy for every captured packet.
        Parses packet layer headers and compiles statistics.
        """
        # Get the packet length in bytes
        packet_len = len(packet)

        # Thread-safe updating of metrics
        with self.lock:
            self.total_packets += 1
            self.total_bytes += packet_len

            # 1. Check Link / Network Layer (IP vs ARP)
            if packet.haslayer(IP):
                src_ip = packet[IP].src
                dst_ip = packet[IP].dst
                self.top_ips[src_ip] += packet_len
                self.top_ips[dst_ip] += packet_len

                # 2. Check Transport Layer protocols
                if packet.haslayer(TCP):
                    proto = "TCP"
                    # Refine service ports (e.g. DNS over TCP)
                    if packet[TCP].sport == 53 or packet[TCP].dport == 53:
                        proto = "DNS"
                elif packet.haslayer(UDP):
                    proto = "UDP"
                    if packet[UDP].sport == 53 or packet[UDP].dport == 53:
                        proto = "DNS"
                elif packet.haslayer(ICMP):
                    proto = "ICMP"
                else:
                    proto = "IP-Other"
            elif packet.haslayer(ARP):
                proto = "ARP"
            else:
                proto = "Other"

            # Increment count and byte size for that protocol
            self.protocol_counts[proto] += 1
            self.protocol_bytes[proto] += packet_len

    def _sniff_loop(self):
        """
        Sniff loop executed inside the background thread.
        """
        # sniff() is a blocking Scapy function
        # store=0 means we do not keep packets in memory (prevents RAM leaks)
        sniff(
            prn=self._packet_callback,
            store=0,
            stop_filter=lambda p: not self.is_running
        )

    def start(self):
        """
        Spawns the background sniffing thread.
        """
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            
            # Reset statistics on start
            self.total_packets = 0
            self.total_bytes = 0
            self.protocol_counts.clear()
            self.protocol_bytes.clear()
            self.top_ips.clear()

        # Target runs in background thread
        self.thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self.thread.start()
        print("[SNIFFER] Background sniffing thread started.")

    def stop(self):
        """
        Stops the background sniffing thread.
        """
        with self.lock:
            self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            print("[SNIFFER] Background sniffing thread stopped.")

    def get_statistics(self) -> Dict:
        """
        Returns a snapshot of the current sniffer metrics.
        Called by the FastAPI thread to stream stats to the UI.
        """
        with self.lock:
            # Sort top talking hosts by volume (bytes) and get top 5
            sorted_ips = sorted(self.top_ips.items(), key=lambda x: x[1], reverse=True)[:5]
            top_hosts = [{"ip": ip, "bytes": size} for ip, size in sorted_ips]
            
            return {
                "total_packets": self.total_packets,
                "total_bytes": self.total_bytes,
                "protocols": {
                    proto: {
                        "packets": count,
                        "bytes": self.protocol_bytes[proto]
                    } for proto, count in self.protocol_counts.items()
                },
                "top_hosts": top_hosts
            }

# Create a singleton sniffer instance to be used across the app
global_sniffer = PacketSniffer()