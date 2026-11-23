from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

GOOD = "x" * 40


def test_short_token_rejected():
    with pytest.raises(ValidationError):
        Settings(token="short", _env_file=None)


def test_missing_token_rejected(monkeypatch):
    monkeypatch.delenv("DESK_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_are_loopback():
    s = Settings(token=GOOD, _env_file=None)
    assert s.host == "127.0.0.1"
    assert s.port == 8787
    assert s.is_loopback()


def test_comma_separated_lists_from_env(monkeypatch):
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    monkeypatch.setenv("DESK_ALLOWED_ORIGINS", "http://a:1, http://b:2")
    monkeypatch.setenv("DESK_ALLOWED_HOSTS", "127.0.0.1,localhost")
    monkeypatch.setenv("DESK_AUDIT_PATHS", "")
    s = Settings(_env_file=None)
    assert s.allowed_origins == ["http://a:1", "http://b:2"]
    assert s.allowed_hosts == ["127.0.0.1", "localhost"]
    assert s.audit_paths == []


def test_empty_geoip_means_none(monkeypatch):
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    monkeypatch.setenv("DESK_GEOIP_DB", "")
    assert Settings(_env_file=None).geoip_db is None


def test_non_loopback_detected():
    assert not Settings(token=GOOD, host="0.0.0.0", _env_file=None).is_loopback()
    assert Settings(token=GOOD, host="::1", _env_file=None).is_loopback()
    assert Settings(token=GOOD, host="localhost", _env_file=None).is_loopback()


def test_audit_paths_parsed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    monkeypatch.setenv("DESK_AUDIT_PATHS", f"{tmp_path},{tmp_path}")
    assert Settings(_env_file=None).audit_paths == [tmp_path, tmp_path]
