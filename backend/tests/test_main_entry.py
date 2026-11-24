"""`python -m app` の起動判定（Issue #12）。uvicorn は実際には起動しない。"""

import pytest

from app import __main__ as entry

GOOD = "x" * 40


@pytest.fixture
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append(kw))
    for key in ("DESK_HOST", "DESK_ALLOW_REMOTE", "DESK_COOKIE_SECURE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DESK_TOKEN", GOOD)
    # 開発者の .env を読まないようにする
    monkeypatch.setitem(entry.Settings.model_config, "env_file", None)
    return calls


def test_refuses_remote_bind_without_permission(started, monkeypatch, capsys):
    monkeypatch.setenv("DESK_HOST", "0.0.0.0")
    assert entry.main() == 2
    assert started == []
    err = capsys.readouterr().err
    assert "DESK_ALLOW_REMOTE=true" in err
    assert GOOD not in err  # エラー表示にトークンを出さない


def test_refuses_remote_bind_without_secure_cookie(started, monkeypatch, capsys):
    monkeypatch.setenv("DESK_HOST", "0.0.0.0")
    monkeypatch.setenv("DESK_ALLOW_REMOTE", "true")
    assert entry.main() == 2
    assert started == []
    assert "DESK_COOKIE_SECURE=true" in capsys.readouterr().err


def test_starts_on_loopback(started):
    assert entry.main() == 0
    assert started and started[0]["host"] == "127.0.0.1"


def test_starts_remote_with_explicit_flags(started, monkeypatch):
    monkeypatch.setenv("DESK_HOST", "0.0.0.0")
    monkeypatch.setenv("DESK_ALLOW_REMOTE", "true")
    monkeypatch.setenv("DESK_COOKIE_SECURE", "true")
    assert entry.main() == 0
    assert started[0]["host"] == "0.0.0.0"
