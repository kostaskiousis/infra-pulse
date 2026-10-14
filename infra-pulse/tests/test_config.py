import json

import pytest

from app.config import Settings, load_targets


def test_reads_valid_targets(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps([{"name": "Router", "host": "192.168.1.1"}, {"name": "DNS", "host": "dns.google"}]))
    targets = load_targets(str(path))
    assert [target.host for target in targets] == ["192.168.1.1", "dns.google"]


def test_rejects_duplicate_hosts(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps([{"name": "A", "host": "1.1.1.1"}, {"name": "B", "host": "1.1.1.1"}]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_targets(str(path))


def test_rejects_invalid_hostname(tmp_path):
    path = tmp_path / "targets.json"
    path.write_text(json.dumps([{"name": "Bad", "host": "somehost; rm -rf /"}]))
    with pytest.raises(ValueError, match="Invalid"):
        load_targets(str(path))


def test_settings_validates_interval(monkeypatch):
    monkeypatch.setenv("MONITOR_INTERVAL", "2")
    with pytest.raises(ValueError, match="MONITOR_INTERVAL"):
        Settings.from_env()
