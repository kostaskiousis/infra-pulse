"""SQLite storage, isolated from the asyncio event loop."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    async def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS system_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    cpu_percent REAL NOT NULL, ram_percent REAL NOT NULL,
                    disk_percent REAL NOT NULL, rx_mbps REAL NOT NULL,
                    tx_mbps REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS device_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL, name TEXT NOT NULL, host TEXT NOT NULL,
                    status TEXT NOT NULL, packet_loss REAL NOT NULL,
                    latency_ms REAL, error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_device_host_time
                    ON device_samples(host, id DESC);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL, level TEXT NOT NULL,
                    category TEXT NOT NULL, target TEXT NOT NULL,
                    message TEXT NOT NULL
                );
            """)

    async def save_cycle(self, ts: str, system: dict, devices: list[dict], events: list[dict]) -> None:
        async with self.lock:
            await asyncio.to_thread(self._save_sync, ts, system, devices, events)

    def _save_sync(self, ts: str, system: dict, devices: list[dict], events: list[dict]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO system_samples (ts, cpu_percent, ram_percent, disk_percent, rx_mbps, tx_mbps) VALUES (?,?,?,?,?,?)",
                (ts, system["cpu_percent"], system["ram_percent"], system["disk_percent"], system["rx_mbps"], system["tx_mbps"]),
            )
            db.executemany(
                "INSERT INTO device_samples (ts,name,host,status,packet_loss,latency_ms,error) VALUES (?,?,?,?,?,?,?)",
                [(ts, d["name"], d["host"], d["status"], d["packet_loss"], d["latency_ms"], d["error"]) for d in devices],
            )
            db.executemany(
                "INSERT INTO events (ts,level,category,target,message) VALUES (?,?,?,?,?)",
                [(e["ts"], e["level"], e["category"], e["target"], e["message"]) for e in events],
            )

    async def recent_history(self, host: str | None = None, limit: int = 80) -> list[dict]:
        limit = max(1, min(limit, 500))
        return await asyncio.to_thread(self._recent_history_sync, host, limit)

    def _recent_history_sync(self, host: str | None, limit: int) -> list[dict]:
        with self._connect() as db:
            if host is None:
                rows = db.execute("SELECT * FROM system_samples ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM device_samples WHERE host=? ORDER BY id DESC LIMIT ?", (host, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    async def recent_events(self, limit: int = 30) -> list[dict]:
        return await asyncio.to_thread(self._recent_events_sync, max(1, min(limit, 100)))

    def _recent_events_sync(self, limit: int) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    async def prune(self, cutoff: str) -> None:
        async with self.lock:
            await asyncio.to_thread(self._prune_sync, cutoff)

    def _prune_sync(self, cutoff: str) -> None:
        with self._connect() as db:
            for table in ("system_samples", "device_samples", "events"):
                db.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
