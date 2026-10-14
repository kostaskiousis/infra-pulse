from app.alerts import AlertEngine
from app.config import Settings


def device(status, loss=0):
    return {"name": "Router", "host": "192.168.1.1", "status": status, "packet_loss": loss}


def resources(cpu=20, ram=25, disk=30):
    return {"cpu_percent": cpu, "ram_percent": ram, "disk_percent": disk}


def test_down_alert_only_after_confirmed_failures_and_recovers():
    engine = AlertEngine(Settings(failure_threshold=2))
    assert engine.evaluate(resources(), [device("down", 100)]) == []
    alerts = engine.evaluate(resources(), [device("down", 100)])
    assert len(alerts) == 1 and alerts[0]["level"] == "critical"
    assert engine.evaluate(resources(), [device("down", 100)]) == []
    alerts = engine.evaluate(resources(), [device("up")])
    assert len(alerts) == 1 and alerts[0]["level"] == "resolved"


def test_resource_threshold_and_hysteresis():
    engine = AlertEngine(Settings(cpu_alert=80))
    assert len(engine.evaluate(resources(cpu=85), [])) == 1
    assert engine.evaluate(resources(cpu=79), []) == []
    assert len(engine.evaluate(resources(cpu=74), [])) == 1


def test_probe_error_does_not_trigger_device_outage():
    engine = AlertEngine(Settings(failure_threshold=1))
    assert engine.evaluate(resources(), [device("error", 100)]) == []


def test_packet_loss_warning_and_recovery():
    engine = AlertEngine(Settings(loss_alert=50))
    assert len(engine.evaluate(resources(), [device("degraded", 66.7)])) == 1
    assert engine.evaluate(resources(), [device("degraded", 66.7)]) == []
    assert engine.evaluate(resources(), [device("up")])[0]["level"] == "resolved"
