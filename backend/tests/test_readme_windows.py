"""README の Windows 11 手順が、実機でつまずいた点を踏まえた内容になっていることを確認する（Issue #20）。"""

import re

from app.config import REPO_DIR

README = (REPO_DIR / "README.md").read_text(encoding="utf-8")
WINDOWS = README.split("## セットアップ（Windows 11）", 1)[1].split("\n## ", 1)[0]
COMMANDS = "\n".join(re.findall(r"```powershell\n(.*?)```", WINDOWS, flags=re.S))


def test_uses_python_not_py_launcher():
    assert not re.search(r"(^|\s)py\s+-m\b", COMMANDS, flags=re.M)
    assert "python -m venv backend\\.venv" in COMMANDS


def test_uses_npm_cmd_and_does_not_loosen_execution_policy():
    assert "npm.cmd ci" in COMMANDS and "npm.cmd run build" in COMMANDS
    assert not re.search(r"(^|\s)npm\s", COMMANDS, flags=re.M)  # npm.ps1 は実行ポリシーで止まる
    assert "Set-ExecutionPolicy" not in COMMANDS


def test_event_log_readers_by_sid_with_admin_and_check():
    assert "Add-LocalGroupMember -SID S-1-5-32-573 -Member $env:USERNAME" in COMMANDS
    assert "Get-LocalGroupMember -SID S-1-5-32-573" in COMMANDS
    assert "管理者" in WINDOWS and "Windows キー + X" in WINDOWS


def test_build_comes_before_start():
    assert COMMANDS.index("npm.cmd run build") < COMMANDS.index("python -m app")


def test_geoip_manual_fallback_documented():
    assert "403" in WINDOWS
    assert "https://db-ip.com/db/download/ip-to-country-lite" in WINDOWS


def test_warns_about_sharing_screenshots():
    assert "トークン" in WINDOWS and "スクリーンショット" in WINDOWS
