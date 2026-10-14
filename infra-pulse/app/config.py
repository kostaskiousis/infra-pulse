"""Runtime configuration and monitored target validation."""
from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

VALID_HOST = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$")


@dataclass(frozen=True)
class Target:
    name: str
    host: str


@dataclass(frozen=True)
class Settings:
    interval: int = 15
    ping_count: int = 3
    failure_threshold: int = 2
    cpu_alert: float = 90.0
    ram_alert: float = 90.0
    disk_alert: float = 90.0
    loss_alert: float = 50.0
    db_path: str = "data/monitor.db"
    targets_path: str = "config/targets.json"
    disk_path: str = os.path.abspath(os.sep)
    retention_days: int = 14
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        def integer(name: str, default: int, minimum: int = 1) -> int:
            value = int(os.getenv(name, str(default)))
            if value < minimum:
                raise ValueError(f"{name} must be >= {minimum}")
            return value

        def percentage(name: str, default: float) -> float:
            value = float(os.getenv(name, str(default)))
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
            return value

        return cls(
            interval=integer("MONITOR_INTERVAL", 15, 5),
            ping_count=integer("MONITOR_PING_COUNT", 3),
            failure_threshold=integer("MONITOR_FAILURE_THRESHOLD", 2),
            cpu_alert=percentage("MONITOR_CPU_ALERT", 90),
            ram_alert=percentage("MONITOR_RAM_ALERT", 90),
            disk_alert=percentage("MONITOR_DISK_ALERT", 90),
            loss_alert=percentage("MONITOR_LOSS_ALERT", 50),
            db_path=os.getenv("MONITOR_DB_PATH", "data/monitor.db"),
            targets_path=os.getenv("MONITOR_TARGETS_PATH", "config/targets.json"),
            disk_path=os.getenv("MONITOR_DISK_PATH", os.path.abspath(os.sep)),
            retention_days=integer("MONITOR_RETENTION_DAYS", 14),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )


def load_targets(path: str) -> list[Target]:
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Targets configuration must be a JSON list")
    targets: list[Target] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each target must be an object")
        name, host = entry.get("name"), entry.get("host")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Each target needs a name (1-80 characters)")
        if not isinstance(host, str) or not host or len(host) > 253:
            raise ValueError("Each target needs a valid hostname or IP")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not VALID_HOST.fullmatch(host) or ".." in host:
                raise ValueError(f"Invalid hostname: {host}") from None
        if host in seen:
            raise ValueError(f"Duplicate target host: {host}")
        seen.add(host)
        targets.append(Target(name=name.strip(), host=host))
    if len(targets) > 100:
        raise ValueError("At most 100 monitored targets are supported")
    return targets
