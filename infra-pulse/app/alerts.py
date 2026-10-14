"""Threshold and state-transition based alert detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import Settings


def event(level: str, category: str, target: str, message: str) -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level, "category": category, "target": target, "message": message,
    }


@dataclass
class AlertEngine:
    settings: Settings
    failure_streak: dict[str, int] = field(default_factory=dict)
    device_down_active: set[str] = field(default_factory=set)
    packet_loss_active: set[str] = field(default_factory=set)
    resource_active: set[str] = field(default_factory=set)

    def evaluate(self, system: dict, devices: list[dict]) -> list[dict]:
        alerts: list[dict] = []
        for device in devices:
            host, name, status, loss = device["host"], device["name"], device["status"], device["packet_loss"]
            if status == "error":  # Probe errors aren't evidence of a device outage.
                continue
            if status == "down":
                self.failure_streak[host] = self.failure_streak.get(host, 0) + 1
                if self.failure_streak[host] >= self.settings.failure_threshold and host not in self.device_down_active:
                    self.device_down_active.add(host)
                    alerts.append(event("critical", "availability", host, f"{name} ({host}) is DOWN"))
            else:
                self.failure_streak[host] = 0
                if host in self.device_down_active:
                    self.device_down_active.remove(host)
                    alerts.append(event("resolved", "availability", host, f"{name} ({host}) is reachable again"))

            if status in ("up", "degraded") and loss >= self.settings.loss_alert and loss > 0:
                if host not in self.packet_loss_active:
                    self.packet_loss_active.add(host)
                    alerts.append(event("warning", "packet_loss", host, f"{name}: packet loss {loss:.1f}%"))
            elif status in ("up", "degraded") and host in self.packet_loss_active:
                self.packet_loss_active.remove(host)
                alerts.append(event("resolved", "packet_loss", host, f"{name}: packet loss recovered ({loss:.1f}%)"))

        for key, threshold in (
            ("cpu_percent", self.settings.cpu_alert),
            ("ram_percent", self.settings.ram_alert),
            ("disk_percent", self.settings.disk_alert),
        ):
            value = system[key]
            label = key.replace("_percent", "").upper()
            if value >= threshold and key not in self.resource_active:
                self.resource_active.add(key)
                alerts.append(event("warning", "resource", label, f"Local {label} usage high: {value:.1f}%"))
            elif value < max(0, threshold - 5) and key in self.resource_active:
                self.resource_active.remove(key)
                alerts.append(event("resolved", "resource", label, f"Local {label} usage recovered: {value:.1f}%"))
        return alerts
