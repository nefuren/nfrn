import subprocess
import sys

import pytest

from app import runner


def test_unknown_command_rejected():
    with pytest.raises(runner.UnknownCommand):
        runner.run("rm -rf /")


def test_commands_are_fixed_tuples():
    for name, argv in runner.COMMANDS.items():
        assert isinstance(argv, tuple), name
        assert all(isinstance(a, str) for a in argv), name


def test_run_uses_list_and_no_shell(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, b"ok", b"")

    monkeypatch.setattr(runner.shutil, "which", lambda exe: f"/usr/bin/{exe}")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    res = runner.run("wevtutil_failures")
    assert res.returncode == 0 and res.stdout == "ok"
    assert isinstance(seen["args"], list)
    assert seen["args"][0] == "/usr/bin/wevtutil"
    assert seen["args"][1:] == list(runner.COMMANDS["wevtutil_failures"][1:])
    assert seen["kwargs"].get("shell", False) is False
    assert "timeout" in seen["kwargs"]


def test_python_placeholder_uses_current_interpreter(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, b"{}", b"")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run("pip_audit_env")
    assert seen["args"][0] == sys.executable


def test_missing_executable(monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda exe: None)
    with pytest.raises(runner.CommandUnavailable):
        runner.run("npm_audit")


def test_cwd_must_be_directory(tmp_path):
    with pytest.raises(ValueError):
        runner.run("npm_audit", cwd=tmp_path / "nope")


def test_decode_never_raises():
    # 不正な UTF-8 や cp932 の日本語でも例外にならない
    assert runner.decode_output("テスト".encode("cp932"))
    assert runner.decode_output(b"\xff\xfe\x00bad") is not None
    assert runner.decode_output("ユーザー".encode()) == "ユーザー"


def test_output_is_truncated(monkeypatch):
    big = b"a" * (runner.MAX_OUTPUT_BYTES + 100)
    monkeypatch.setattr(runner.shutil, "which", lambda exe: f"/usr/bin/{exe}")
    monkeypatch.setattr(
        runner.subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 0, big, b"")
    )
    assert len(runner.run("npm_audit").stdout) == runner.MAX_OUTPUT_BYTES


def test_timeout_is_reported(monkeypatch):
    def boom(args, **kw):
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(runner.shutil, "which", lambda exe: f"/usr/bin/{exe}")
    monkeypatch.setattr(runner.subprocess, "run", boom)
    with pytest.raises(runner.CommandFailed):
        runner.run("npm_audit")
