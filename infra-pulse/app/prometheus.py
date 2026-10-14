"""Prometheus gauges (one process, fixed configured target set)."""
from prometheus_client import Gauge

DEVICE_UP = Gauge("infrapulse_device_up", "Target reachable on last check", ["host", "name"])
DEVICE_LOSS = Gauge("infrapulse_device_packet_loss_percent", "Target ICMP packet loss percent", ["host", "name"])
DEVICE_LATENCY = Gauge("infrapulse_device_latency_ms", "Target ICMP RTT (milliseconds)", ["host", "name"])
CPU = Gauge("infrapulse_system_cpu_percent", "Local CPU usage percent")
RAM = Gauge("infrapulse_system_ram_percent", "Local memory usage percent")
DISK = Gauge("infrapulse_system_disk_percent", "Local disk usage percent")
RX = Gauge("infrapulse_network_receive_mbps", "Aggregate local incoming megabits per second")
TX = Gauge("infrapulse_network_transmit_mbps", "Aggregate local outgoing megabits per second")
LAST_CHECK = Gauge("infrapulse_last_poll_unix", "Last complete monitor poll time")


def update_metrics(system: dict, devices: list[dict], timestamp: float) -> None:
    CPU.set(system["cpu_percent"])
    RAM.set(system["ram_percent"])
    DISK.set(system["disk_percent"])
    RX.set(system["rx_mbps"])
    TX.set(system["tx_mbps"])
    LAST_CHECK.set(timestamp)
    for item in devices:
        labels = (item["host"], item["name"])
        DEVICE_UP.labels(*labels).set(1 if item["status"] in ("up", "degraded") else 0)
        DEVICE_LOSS.labels(*labels).set(item["packet_loss"])
        # NaN marks a missing RTT; zero would imply an instantaneous response.
        DEVICE_LATENCY.labels(*labels).set(
            item["latency_ms"] if item["latency_ms"] is not None else float("nan")
        )
