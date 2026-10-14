import asyncio

import app.probes as probes
from app.config import Target


def test_packet_loss_and_latency(monkeypatch):
    replies = iter([(True, 5.0), (False, None), (True, 9.0)])

    async def fake_ping(_):
        return next(replies)

    monkeypatch.setattr(probes, "ping_once", fake_ping)
    result = asyncio.run(probes.probe_target(Target("Router", "192.168.1.1"), count=3))
    assert result.status == "degraded"
    assert result.packet_loss == 33.3
    assert result.latency_ms == 7.0


def test_probe_error_is_not_a_down_status(monkeypatch):
    async def missing_ping(_):
        raise RuntimeError("OS ping executable was not found")

    monkeypatch.setattr(probes, "ping_once", missing_ping)
    result = asyncio.run(probes.probe_target(Target("Router", "192.168.1.1")))
    assert result.status == "error"
    assert result.error is not None
