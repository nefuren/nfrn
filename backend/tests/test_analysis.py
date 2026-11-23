from datetime import UTC, datetime, timedelta

from app.analysis.alerts import AlertEngine
from app.analysis.score import ScoreContext, compute_score
from app.collectors.history import LoginEvent
from app.collectors.network import Connection

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
ZERO = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "unknown": 0}


def ctx(**kw):
    base = dict(firewall_profiles={"Domain": True, "Private": True, "Public": True}, listening=[],
                failures_1h=0, lockouts_24h=0, vuln_counts=dict(ZERO), dashboard_exposed=False)
    base.update(kw)
    return ScoreContext(**base)


def port(p, exposed=True, proto="tcp", process="x"):
    return {"proto": proto, "address": "0.0.0.0" if exposed else "127.0.0.1", "port": p, "pid": 1,
            "process": process, "exposed": exposed}


# ---------- score ----------

def test_perfect_score():
    s = compute_score(ctx())
    assert s["value"] == 100 and s["items"] == []


def test_firewall_disabled():
    s = compute_score(ctx(firewall_profiles={"Domain": True, "Private": False, "Public": False}))
    assert s["value"] == 75
    assert "Private" in s["items"][0]["label"] and s["items"][0]["points"] == -25


def test_firewall_unknown_is_note_not_deduction():
    s = compute_score(ctx(firewall_profiles={"Domain": None, "Private": None, "Public": None}))
    assert s["value"] == 100 and s["notes"]


def test_risky_and_other_ports():
    listening = [port(3389), port(445), port(5900), port(6379), port(8080), port(8081),
                 port(9999, exposed=False), port(5353, proto="udp")]
    s = compute_score(ctx(listening=listening))
    by = {i["label"].split("：")[0]: i["points"] for i in s["items"]}
    assert by["危険なポートを公開"] == -15  # 4個 × -5 だが上限 -15
    assert by["その他の公開TCPポート"] == -2
    assert s["value"] == 83


def test_login_failures_and_lockouts():
    assert compute_score(ctx(failures_1h=3))["value"] == 95
    assert compute_score(ctx(failures_1h=10))["value"] == 85
    assert compute_score(ctx(lockouts_24h=1))["value"] == 90


def test_vulns_capped():
    counts = dict(ZERO, critical=2, high=1, moderate=1, low=1, unknown=1)
    # critical 2×-10 + high -5 + moderate -2 + low -1 + unknown -1 = -29
    assert compute_score(ctx(vuln_counts=counts))["value"] == 71
    # 上限 -30
    assert compute_score(ctx(vuln_counts=dict(ZERO, critical=9)))["value"] == 70


def test_score_clamped_to_zero():
    s = compute_score(ctx(firewall_profiles={"Domain": False, "Private": False, "Public": False},
                          listening=[port(p) for p in (21, 23, 445, 3389, 8000, 8001, 8002, 8003, 8004, 8005)],
                          failures_1h=50, lockouts_24h=3, vuln_counts=dict(ZERO, critical=9),
                          dashboard_exposed=True))
    assert s["value"] == 0


# ---------- alerts ----------

def fail(i, ip="203.0.113.5", user="guest", seconds=0, kind="failure"):
    return LoginEvent(ts=NOW + timedelta(seconds=seconds), kind=kind, user=user, source_ip=ip,
                      detail="", key=f"k{i}-{ip}-{seconds}")


def test_bruteforce_alert_once_per_cooldown():
    eng = AlertEngine()
    events = [fail(i, seconds=i * 10) for i in range(7)]
    new = eng.evaluate(NOW, events, [], [])
    brute = [a for a in new if a["kind"] == "bruteforce"]
    assert len(brute) == 1 and brute[0]["level"] == "crit"
    assert brute[0]["source_ip"] == "203.0.113.5"
    more = eng.evaluate(NOW, [fail(99, seconds=100)], [], [])
    assert not [a for a in more if a["kind"] == "bruteforce"]


def test_failures_spread_out_do_not_trigger():
    eng = AlertEngine()
    events = [fail(i, seconds=i * 120) for i in range(6)]  # 2分おき
    assert not [a for a in eng.evaluate(NOW, events, [], []) if a["kind"] == "bruteforce"]


def test_admin_target_and_lockout():
    eng = AlertEngine()
    new = eng.evaluate(NOW, [fail(1, user="Administrator"), fail(2, user="山田", kind="lockout")], [], [])
    kinds = {a["kind"]: a for a in new}
    assert kinds["admin_target"]["level"] == "warn"
    assert kinds["lockout"]["level"] == "crit"
    assert "山田" in kinds["lockout"]["message"]


def test_new_listening_port_after_baseline():
    eng = AlertEngine()
    assert eng.evaluate(NOW, [], [port(445)], []) == []  # 初回はベースライン
    new = eng.evaluate(NOW, [], [port(445), port(8080, process="python.exe")], [])
    assert [a["kind"] for a in new] == ["new_port"]
    assert "8080" in new[0]["message"] and "python.exe" in new[0]["message"]
    assert eng.evaluate(NOW, [], [port(445), port(8080)], []) == []


def test_suspicious_outbound():
    eng = AlertEngine()
    conns = [Connection("tcp", 50000, "45.33.32.156", 4444, 10, "evil.exe"),
             Connection("tcp", 50001, "93.184.216.34", 443, 10, "chrome.exe")]
    new = eng.evaluate(NOW, [], [], conns)
    assert [a["kind"] for a in new] == ["suspicious_outbound"]
    assert eng.evaluate(NOW, [], [], conns) == []  # クールダウン


def test_alerts_bounded_and_newest_first():
    eng = AlertEngine(max_alerts=3)
    for i in range(5):
        eng.evaluate(NOW, [fail(i, user="root", ip=f"198.51.100.{i}")], [], [])
    recent = eng.recent(10)
    assert len(recent) == 3
    assert recent[0]["id"] > recent[-1]["id"]


def test_ignored_port_never_alerts():
    eng = AlertEngine(ignore_ports=frozenset({("tcp", 8787)}))
    eng.evaluate(NOW, [], [], [])
    assert eng.evaluate(NOW, [], [port(8787, exposed=False)], []) == []
