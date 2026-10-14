"""Local system and aggregate network adapter measurements."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import psutil


@dataclass
class SystemSample:
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    rx_mbps: float
    tx_mbps: float

    def to_dict(self) -> dict:
        return asdict(self)


class SystemCollector:
    def __init__(self, disk_path: str):
        self.disk_path = disk_path
        psutil.cpu_percent(interval=None)  # Prime first non-blocking CPU sample.
        self.last_net = psutil.net_io_counters()
        self.last_time = time.monotonic()

    def collect(self) -> SystemSample:
        now = time.monotonic()
        net = psutil.net_io_counters()
        elapsed = max(now - self.last_time, 0.001)
        rx_mbps = tx_mbps = 0.0
        if net is not None and self.last_net is not None:
            rx_mbps = max(0, net.bytes_recv - self.last_net.bytes_recv) * 8 / elapsed / 1_000_000
            tx_mbps = max(0, net.bytes_sent - self.last_net.bytes_sent) * 8 / elapsed / 1_000_000
        self.last_net = net
        self.last_time = now
        return SystemSample(
            cpu_percent=round(psutil.cpu_percent(interval=None), 1),
            ram_percent=round(psutil.virtual_memory().percent, 1),
            disk_percent=round(psutil.disk_usage(self.disk_path).percent, 1),
            rx_mbps=round(rx_mbps, 3),
            tx_mbps=round(tx_mbps, 3),
        )
