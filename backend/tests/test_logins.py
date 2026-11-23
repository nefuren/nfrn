from datetime import UTC, datetime, timedelta
from pathlib import Path

from app import runner
from app.collectors.history import LoginEvent, LoginHistory
from app.collectors.logins_linux import LinuxLoginSource, parse_auth_log
from app.collectors.logins_windows import WindowsLoginSource, parse_windows_events

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# ---------- Windows ----------

def test_parse_windows_failures_and_lockout():
    events = parse_windows_events(read("wevtutil_failures.xml"))
    kinds = [e.kind for e in events]
    assert kinds.count("failure") == 3 and kinds.count("lockout") == 1
    first = next(e for e in events if e.key == "win:1001")
    assert first.user == "Administrator"
    assert first.source_ip == "203.0.113.5"
    assert first.ts == datetime(2026, 11, 23, 9, 12, 3, 123456, tzinfo=UTC)
    assert "ネットワーク" in first.detail  # LogonType 3


def test_windows_script_username_kept_as_plain_text():
    events = parse_windows_events(read("wevtutil_failures.xml"))
    e = next(e for e in events if e.key == "win:1002")
    assert e.user == "<script>alert(1)</script>"  # 解釈もエスケープもしない生の文字列


def test_windows_japanese_user_and_dash_ip():
    events = parse_windows_events(read("wevtutil_failures.xml"))
    e = next(e for e in events if e.key == "win:1003")
    assert e.user == "山田"
    assert e.source_ip is None


def test_windows_success_filters_noise():
    events = parse_windows_events(read("wevtutil_success.xml"))
    assert [(e.user, e.kind) for e in events] == [("yamada", "success"), ("yamada", "success")]


def test_windows_bad_xml_does_not_raise():
    assert parse_windows_events("<Event><broken") == []
    assert parse_windows_events("") == []


def test_windows_xxe_rejected():
    evil = '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Event>&e;</Event>'
    assert parse_windows_events(evil) == []


def test_windows_source_access_denied(monkeypatch):
    monkeypatch.setattr(
        runner, "run", lambda name, **kw: runner.CommandResult(5, "", "Access is denied.")
    )
    events, status = WindowsLoginSource().fetch()
    assert events == [] and status["state"] == "no_permission"


def test_windows_source_ok(monkeypatch):
    out = {"wevtutil_failures": read("wevtutil_failures.xml"), "wevtutil_success": read("wevtutil_success.xml")}
    monkeypatch.setattr(runner, "run", lambda name, **kw: runner.CommandResult(0, out[name], ""))
    events, status = WindowsLoginSource().fetch()
    assert status["state"] == "ok" and len(events) == 6


def test_windows_source_missing_tool(monkeypatch):
    def boom(name, **kw):
        raise runner.CommandUnavailable("wevtutil")

    monkeypatch.setattr(runner, "run", boom)
    events, status = WindowsLoginSource().fetch()
    assert status["state"] == "unavailable"


# ---------- Linux ----------

def test_parse_auth_log():
    events = parse_auth_log(read("auth.log"), year=2026)
    summary = [(e.kind, e.user, e.source_ip) for e in events]
    assert summary == [
        ("failure", "admin", "198.51.100.7"),
        ("failure", "root", "198.51.100.7"),
        ("success", "alice", "192.168.1.10"),
        ("failure", "<script>alert(1)</script>", "198.51.100.8"),
        ("failure", "bob", "2001:db8::5"),
    ]
    assert events[1].ts == datetime(2026, 11, 23, 9, 1, 5, 123456, tzinfo=UTC)
    assert all(e.ts.tzinfo is not None for e in events)


def test_linux_source_permission_denied(tmp_path, monkeypatch):
    log = tmp_path / "auth.log"
    log.write_text("x", encoding="utf-8")
    log.chmod(0)
    src = LinuxLoginSource(log)
    monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    events, status = src.fetch()
    assert status["state"] == "no_permission"


def test_linux_source_reads_file(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text(read("auth.log"), encoding="utf-8")
    events, status = LinuxLoginSource(log).fetch()
    assert status["state"] == "ok" and len(events) == 5


# ---------- History ----------

def ev(key, minutes_ago, kind="failure", now=None, ip="203.0.113.1", user="u"):
    now = now or datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    return LoginEvent(ts=now - timedelta(minutes=minutes_ago), kind=kind, user=user, source_ip=ip,
                      detail="", key=key)


def test_history_dedupes_and_returns_only_new():
    h = LoginHistory()
    assert len(h.add([ev("a", 1), ev("b", 2)])) == 2
    assert [e.key for e in h.add([ev("a", 1), ev("c", 3)])] == ["c"]


def test_history_failures_per_minute():
    now = datetime(2026, 11, 23, 12, 0, 30, tzinfo=UTC)
    h = LoginHistory()
    h.add([ev("a", 0, now=now), ev("b", 0, now=now), ev("c", 5, now=now), ev("d", 90, now=now),
           ev("e", 1, kind="success", now=now)])
    buckets = h.failures_per_minute(now, minutes=60)
    assert len(buckets) == 60
    assert buckets[-1] == 2
    assert buckets[-6] == 1
    assert sum(buckets) == 3


def test_history_count_since():
    now = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    h = LoginHistory()
    h.add([ev("a", 10, now=now), ev("b", 100, now=now), ev("c", 5, kind="lockout", now=now)])
    assert h.count("failure", now - timedelta(hours=1)) == 1
    assert h.count("lockout", now - timedelta(hours=24)) == 1


def test_history_is_bounded():
    h = LoginHistory(max_events=10)
    h.add([ev(str(i), i) for i in range(50)])
    assert len(h.recent(100)) == 10


def test_event_to_dict_is_json_ready():
    d = ev("a", 0).to_dict()
    assert d["ts"].endswith("+00:00") and d["kind"] == "failure"
