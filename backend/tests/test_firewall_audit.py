from pathlib import Path

from app import runner
from app.collectors.audit import AuditRunner, parse_npm_audit, parse_pip_audit
from app.collectors.firewall import firewall_state

FIX = Path(__file__).parent / "fixtures"


def test_firewall_policy_overrides_local():
    values = {
        ("policy", "DomainProfile"): None,
        ("local", "DomainProfile"): 1,
        ("policy", "PrivateProfile"): 0,  # GPO で無効
        ("local", "PrivateProfile"): 1,
        ("policy", "PublicProfile"): None,
        ("local", "PublicProfile"): 1,
    }
    st = firewall_state(reader=lambda scope, profile: values[(scope, profile)])
    assert st == {"available": True, "profiles": {"Domain": True, "Private": False, "Public": True}}


def test_firewall_unknown_when_unreadable():
    st = firewall_state(reader=lambda scope, profile: None)
    assert st["profiles"] == {"Domain": None, "Private": None, "Public": None}


def test_firewall_non_windows():
    assert firewall_state(reader=None, is_windows=False) == {"available": False, "profiles": {}}


def test_parse_pip_audit():
    findings = parse_pip_audit((FIX / "pip_audit.json").read_text(), project="backend")
    assert len(findings) == 1
    f = findings[0]
    assert (f.source, f.package, f.version, f.vuln_id, f.fix) == (
        "pip", "requests", "2.19.0", "PYSEC-2018-28", "2.20.0"
    )
    assert f.aliases == ["CVE-2018-18074"]
    assert f.severity == "unknown"


def test_parse_npm_audit():
    findings = parse_npm_audit((FIX / "npm_audit.json").read_text(), project="frontend")
    by_pkg = {f.package: f for f in findings}
    assert by_pkg["nanoid"].vuln_id == "GHSA-mwcw-c2x4-8c55"
    assert by_pkg["nanoid"].severity == "moderate"
    assert by_pkg["postcss"].vuln_id == "via nanoid"
    assert by_pkg["postcss"].fix == "vite@6.0.0"


def test_parse_garbage_returns_empty():
    assert parse_pip_audit("not json", project="x") == []
    assert parse_npm_audit("{}", project="x") == []


def test_audit_runner_handles_missing_tools(monkeypatch, tmp_path):
    def boom(name, **kw):
        raise runner.CommandUnavailable(name)

    monkeypatch.setattr(runner, "run", boom)
    (tmp_path / "package-lock.json").write_text("{}")
    report = AuditRunner(frontend_dir=tmp_path, extra_paths=[]).run_once()
    assert report["findings"] == []
    assert {t["state"] for t in report["targets"]} == {"unavailable"}


def test_audit_runner_collects(monkeypatch, tmp_path):
    out = {
        "pip_audit_env": runner.CommandResult(1, (FIX / "pip_audit.json").read_text(), ""),
        "npm_audit": runner.CommandResult(1, (FIX / "npm_audit.json").read_text(), ""),
    }
    monkeypatch.setattr(runner, "run", lambda name, **kw: out[name])
    (tmp_path / "package-lock.json").write_text("{}")
    report = AuditRunner(frontend_dir=tmp_path, extra_paths=[]).run_once()
    assert len(report["findings"]) == 3
    assert all(t["state"] == "ok" for t in report["targets"])
    assert report["counts"] == {"critical": 0, "high": 0, "moderate": 2, "low": 0, "unknown": 1}


def test_audit_runner_extra_paths(monkeypatch, tmp_path):
    calls = []

    def fake(name, cwd=None, **kw):
        calls.append((name, cwd))
        return runner.CommandResult(0, '{"dependencies": []}' if "pip" in name else '{"vulnerabilities": {}}', "")

    monkeypatch.setattr(runner, "run", fake)
    py = tmp_path / "py"
    py.mkdir()
    (py / "requirements.txt").write_text("requests==2.32.3")
    js = tmp_path / "js"
    js.mkdir()
    (js / "package-lock.json").write_text("{}")
    AuditRunner(frontend_dir=tmp_path / "nofront", extra_paths=[py, js, tmp_path / "missing"]).run_once()
    assert ("pip_audit_requirements", py) in calls
    assert ("npm_audit", js) in calls
