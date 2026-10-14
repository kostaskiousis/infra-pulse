import asyncio

from app.storage import Storage


def test_sqlite_history_and_events(tmp_path):
    async def run():
        storage = Storage(str(tmp_path / "monitor.db"))
        await storage.initialize()
        sample = {"cpu_percent": 10, "ram_percent": 20, "disk_percent": 30, "rx_mbps": 1, "tx_mbps": 2}
        devices = [{"name": "DNS", "host": "1.1.1.1", "status": "up", "packet_loss": 0, "latency_ms": 4, "error": None}]
        alerts = [{"ts": "2026-01-01T12:00:00+00:00", "level": "resolved", "category": "resource", "target": "CPU", "message": "Recovered"}]
        await storage.save_cycle("2026-01-01T12:00:00+00:00", sample, devices, alerts)
        assert (await storage.recent_history())[0]["cpu_percent"] == 10
        assert (await storage.recent_history(host="1.1.1.1"))[0]["latency_ms"] == 4
        assert (await storage.recent_events())[0]["message"] == "Recovered"
        await storage.prune("2026-01-02T00:00:00+00:00")
        assert await storage.recent_history() == []
        assert await storage.recent_events() == []
    asyncio.run(run())
