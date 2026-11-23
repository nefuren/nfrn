"""Linux の sshd 認証ログ（auth.log または journalctl）を読む。"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .. import runner
from .history import LoginEvent, clip

TAIL_BYTES = 2 * 1024 * 1024

_FAILED = re.compile(
    r"sshd\[\d+\]: Failed (password|publickey|keyboard-interactive/pam) for (invalid user )?(\S+) "
    r"from (\S+) port \d+"
)
_ACCEPTED = re.compile(r"sshd\[\d+\]: Accepted (\S+) for (\S+) from (\S+) port \d+")
_SYSLOG_TS = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2}) (\d{2}):(\d{2}):(\d{2}) ")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _parse_ts(line: str, year: int, now: datetime) -> datetime | None:
    first = line.split(" ", 1)[0]
    if "T" in first and first[:4].isdigit():
        try:
            ts = datetime.fromisoformat(first)
        except ValueError:
            return None
        return (ts if ts.tzinfo else ts.astimezone()).astimezone(UTC)
    m = _SYSLOG_TS.match(line)
    if not m or m.group(1) not in _MONTHS:
        return None
    try:
        local = datetime(year, _MONTHS[m.group(1)], int(m.group(2)),
                         int(m.group(3)), int(m.group(4)), int(m.group(5))).astimezone()
    except ValueError:
        return None
    if local > now + timedelta(days=1):  # 年をまたいだ古い行
        local = local.replace(year=year - 1)
    return local.astimezone(UTC)


def _key(line: str) -> str:
    return "lnx:" + hashlib.blake2b(line.encode("utf-8", "replace"), digest_size=10).hexdigest()


def parse_auth_log(text: str, year: int | None = None) -> list[LoginEvent]:
    now = datetime.now(UTC)
    year = year or now.astimezone().year
    events: list[LoginEvent] = []
    for line in text.splitlines():
        if "sshd[" not in line:
            continue
        if m := _FAILED.search(line):
            method, invalid, user, ip = m.groups()
            kind, detail = "failure", f"SSH {method} 失敗" + ("（存在しないユーザー）" if invalid else "")
        elif m := _ACCEPTED.search(line):
            method, user, ip = m.groups()
            kind, detail = "success", f"SSH {method} ログイン"
        else:
            continue
        ts = _parse_ts(line, year, now)
        if ts is None:
            continue
        events.append(LoginEvent(ts=ts, kind=kind, user=clip(user), source_ip=clip(ip, 45),
                                 detail=detail, key=_key(line)))
    return events


def _status(state: str, message: str = "", source: str = "") -> dict:
    return {"state": state, "message": message, "source": source}


class LinuxLoginSource:
    def __init__(self, auth_log: Path) -> None:
        self.auth_log = auth_log

    def fetch(self) -> tuple[list[LoginEvent], dict]:
        if self.auth_log.exists():
            src = str(self.auth_log)
            try:
                with self.auth_log.open("rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - TAIL_BYTES))
                    data = f.read()
            except PermissionError:
                return [], _status("no_permission", "ログを読む権限がありません（adm グループへの追加が必要）", src)
            except OSError as exc:
                return [], _status("error", exc.__class__.__name__, src)
            return parse_auth_log(runner.decode_output(data)), _status("ok", source=src)

        try:
            res = runner.run("journal_sshd", timeout=20)
        except runner.CommandUnavailable:
            return [], _status("unavailable", "auth.log も journalctl も見つかりません", "journalctl")
        except runner.CommandFailed as exc:
            return [], _status("error", str(exc), "journalctl")
        if res.returncode != 0 and not res.stdout:
            return [], _status("no_permission", "journal を読む権限がありません", "journalctl")
        return parse_auth_log(res.stdout), _status("ok", source="journalctl")
