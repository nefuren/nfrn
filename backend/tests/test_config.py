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
    assert not Settings(
        token=GOOD, host="0.0.0.0", allow_remote=True, cookie_secure=True, _env_file=None
    ).is_loopback()
    assert Settings(token=GOOD, host="::1", _env_file=None).is_loopback()
    assert Settings(token=GOOD, host="localhost", _env_file=None).is_loopback()


def test_audit_paths_parsed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    monkeypatch.setenv("DESK_AUDIT_PATHS", f"{tmp_path},{tmp_path}")
    assert Settings(_env_file=None).audit_paths == [tmp_path, tmp_path]


# ---------- 外部公開には明示的な許可が必要（Issue #12） ----------

@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_loopback_starts_without_extra_flags(host):
    s = Settings(token=GOOD, host=host, _env_file=None)
    assert s.is_loopback() and s.allow_remote is False


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.10", "desk.example"])
def test_remote_bind_requires_allow_remote(host):
    with pytest.raises(ValidationError) as exc:
        Settings(token=GOOD, host=host, cookie_secure=True, _env_file=None)
    assert "DESK_ALLOW_REMOTE=true" in str(exc.value)


def test_remote_bind_requires_secure_cookie():
    with pytest.raises(ValidationError) as exc:
        Settings(token=GOOD, host="0.0.0.0", allow_remote=True, _env_file=None)
    assert "DESK_COOKIE_SECURE=true" in str(exc.value)


def test_remote_bind_allowed_with_both_flags():
    s = Settings(token=GOOD, host="0.0.0.0", allow_remote=True, cookie_secure=True, _env_file=None)
    assert not s.is_loopback()


def test_remote_flags_from_env(monkeypatch):
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    monkeypatch.setenv("DESK_HOST", "0.0.0.0")
    monkeypatch.setenv("DESK_ALLOW_REMOTE", "true")
    monkeypatch.setenv("DESK_COOKIE_SECURE", "true")
    s = Settings(_env_file=None)
    assert s.allow_remote and s.cookie_secure


def test_allow_remote_alone_does_not_matter_on_loopback():
    # ループバックなら DESK_ALLOW_REMOTE の有無にかかわらず起動できる
    assert Settings(token=GOOD, host="127.0.0.1", allow_remote=True, _env_file=None).is_loopback()
