"""OS コマンド実行の唯一の入口。

- 実行できるのは COMMANDS に書いた固定の引数タプルだけ。呼び出し側は名前で指定する。
- shell=True は使わない。外部入力を引数に混ぜない（可変なのは作業ディレクトリ cwd のみ）。
- 実行ファイルは shutil.which で絶対パスに解決してから起動する。
"""

from __future__ import annotations

import locale
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PYTHON = "{python}"
MAX_OUTPUT_BYTES = 5 * 1024 * 1024

# Windows: Security ログを直近24時間・新しい順に取得。
# 失敗(4625)/ロックアウト(4740)と、人の操作による成功(4624: 対話型/ロック解除/RDP/キャッシュ)を分けて取る
# （成功はサービスのログオンが大量にあり、まとめると失敗が埋もれるため）。
_LAST_24H = "TimeCreated[timediff(@SystemTime) <= 86400000]"
_WEVT_FAILURES = f"*[System[(EventID=4625 or EventID=4740) and {_LAST_24H}]]"
_WEVT_SUCCESS = (
    f"*[System[(EventID=4624) and {_LAST_24H}]] and *[EventData[Data[@Name='LogonType']='2' or "
    "Data[@Name='LogonType']='7' or Data[@Name='LogonType']='10' or Data[@Name='LogonType']='11']]"
)

COMMANDS: dict[str, tuple[str, ...]] = {
    "wevtutil_failures": ("wevtutil", "qe", "Security", f"/q:{_WEVT_FAILURES}", "/f:xml", "/c:500", "/rd:true"),
    "wevtutil_success": ("wevtutil", "qe", "Security", f"/q:{_WEVT_SUCCESS}", "/f:xml", "/c:100", "/rd:true"),
    "journal_sshd": (
        "journalctl", "--no-pager", "-o", "short-iso", "--since=-24h", "_COMM=sshd",
    ),
    "pip_audit_env": (PYTHON, "-m", "pip_audit", "-f", "json", "--progress-spinner", "off", "--skip-editable"),
    "pip_audit_requirements": (
        PYTHON, "-m", "pip_audit", "-f", "json", "--progress-spinner", "off", "-r", "requirements.txt",
    ),
    "npm_audit": ("npm", "audit", "--json"),
}


class UnknownCommand(ValueError):
    pass


class CommandUnavailable(RuntimeError):
    pass


class CommandFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def decode_output(data: bytes) -> str:
    """UTF-8 を優先し、駄目ならOSの既定エンコーディング（日本語Windowsは cp932）で読む。例外は出さない。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    enc = locale.getpreferredencoding(False) or "utf-8"
    try:
        return data.decode(enc)
    except (UnicodeDecodeError, LookupError):
        return data.decode("utf-8", errors="replace")


def _resolve(argv: tuple[str, ...]) -> list[str]:
    exe = argv[0]
    if exe == PYTHON:
        return [sys.executable, *argv[1:]]
    path = shutil.which(exe)
    if path is None:
        raise CommandUnavailable(f"{exe} が見つかりません")
    return [path, *argv[1:]]


def run(name: str, cwd: Path | None = None, timeout: float = 30) -> CommandResult:
    try:
        argv = COMMANDS[name]
    except KeyError:
        raise UnknownCommand(name) from None
    if cwd is not None and not Path(cwd).is_dir():
        raise ValueError(f"cwd がディレクトリではありません: {cwd}")
    args = _resolve(argv)
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            shell=False,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandFailed(f"{name}: タイムアウト（{timeout}秒）") from exc
    except OSError as exc:
        raise CommandFailed(f"{name}: 起動できません ({exc.__class__.__name__})") from exc
    return CommandResult(
        returncode=proc.returncode,
        stdout=decode_output(proc.stdout[:MAX_OUTPUT_BYTES]),
        stderr=decode_output(proc.stderr[:MAX_OUTPUT_BYTES]),
    )
