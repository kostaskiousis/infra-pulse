"""Periodic polling orchestration; intentionally single worker/process."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from .alerts import AlertEngine
from .config import Settings, Target
from .notifier import Notifier
from .probes import probe_target
from .prometheus import update_metrics
from .storage import Storage
from .system import SystemCollector

logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self, settings: Settings, targets: list[Target], storage: Storage):
        self.settings = settings
        self.targets = targets
        self.storage = storage
        self.alerts = AlertEngine(settings)
        self.notifier = Notifier(settings)
        self.collector = SystemCollector(settings.disk_path)
        self.devices: list[dict] = []
        self.system: dict | None = None
        self.last_check: str | None = None
        self.last_error: str | None = None
        self.cycles = 0
        self._concurrency = asyncio.Semaphore(15)

    async def _probe(self, target: Target) -> dict:
        async with self._concurrency:
            return (await probe_target(target, self.settings.ping_count)).to_dict()

    async def poll(self) -> None:
        timestamp = datetime.now(timezone.utc)
        devices = await asyncio.gather(*(self._probe(target) for target in self.targets))
        system = self.collector.collect().to_dict()
        new_events = self.alerts.evaluate(system, devices)
        checked_at = timestamp.isoformat(timespec="seconds")
        await self.storage.save_cycle(checked_at, system, devices, new_events)
        update_metrics(system, devices, time.time())
        self.devices = devices
        self.system = system
        self.last_check = checked_at
        self.last_error = None
        self.cycles += 1
        if new_events:
            await asyncio.gather(*(self.notifier.send(item) for item in new_events))

    async def run(self) -> None:
        while True:
            began = time.monotonic()
            try:
                await self.poll()
                if self.cycles % max(1, round(86400 / self.settings.interval)) == 0:
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=self.settings.retention_days)).isoformat(timespec="seconds")
                    await self.storage.prune(cutoff)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("Monitor polling failed")
            await asyncio.sleep(max(1.0, self.settings.interval - (time.monotonic() - began)))

    def overview(self) -> dict:
        up = sum(1 for device in self.devices if device["status"] == "up")
        degraded = sum(1 for device in self.devices if device["status"] == "degraded")
        down = sum(1 for device in self.devices if device["status"] == "down")
        errors = sum(1 for device in self.devices if device["status"] == "error")
        return {
            "name": "InfraPulse",
            "last_check": self.last_check,
            "interval_seconds": self.settings.interval,
            "poll_error": self.last_error,
            "targets": len(self.targets),
            "up": up, "degraded": degraded, "down": down, "errors": errors,
            "devices": self.devices,
            "system": self.system,
        }
