"""怪しい通信やログイン試行の検知ルール。"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from ..collectors.history import LoginEvent, clip
from ..collectors.network import Connection

BRUTE_WINDOW = timedelta(minutes=5)
BRUTE_THRESHOLD = 5
BRUTE_COOLDOWN = timedelta(minutes=10)
ADMIN_USERS = {"administrator", "admin", "root"}
ADMIN_COOLDOWN = timedelta(minutes=10)
SUSPICIOUS_REMOTE_PORTS = {23: "Telnet", 1337: "", 4444: "Metasploit既定", 5555: "", 6667: "IRC", 31337: ""}
OUTBOUND_COOLDOWN = timedelta(minutes=30)


class AlertEngine:
    def __init__(self, max_alerts: int = 200, ignore_ports: frozenset[tuple[str, int]] = frozenset()) -> None:
        self._ignore_ports = ignore_ports  # 例: ダッシュボード自身の待ち受け
        self._alerts: deque[dict] = deque(maxlen=max_alerts)
        self._next_id = 1
        self._fail_times: dict[str, deque[datetime]] = {}
        self._cooldown: dict[tuple, datetime] = {}
        self._known_ports: set[tuple[str, int]] | None = None

    def _cooling(self, key: tuple, at: datetime, period: timedelta) -> bool:
        last = self._cooldown.get(key)
        if last is not None and at - last < period:
            return True
        self._cooldown[key] = at
        return False

    def _emit(self, out: list[dict], at: datetime, level: str, kind: str, message: str,
              source_ip: str | None = None) -> None:
        alert = {"id": self._next_id, "ts": at.isoformat(), "level": level, "kind": kind,
                 "message": message, "source_ip": source_ip}
        self._next_id += 1
        self._alerts.append(alert)
        out.append(alert)

    def evaluate(self, now: datetime, new_events: list[LoginEvent], listening: list[dict],
                 connections: list[Connection]) -> list[dict]:
        out: list[dict] = []
        for e in sorted(new_events, key=lambda e: e.ts):
            if e.kind == "lockout":
                self._emit(out, e.ts, "crit", "lockout", f"アカウント「{clip(e.user, 40)}」がロックされました")
                continue
            if e.kind != "failure":
                continue
            ip = e.source_ip or "-"
            if e.user.lower() in ADMIN_USERS and not self._cooling(("admin", ip, e.user.lower()), e.ts,
                                                                   ADMIN_COOLDOWN):
                self._emit(out, e.ts, "warn", "admin_target",
                           f"管理者アカウント「{clip(e.user, 40)}」へのログイン失敗（{ip}）", e.source_ip)
            if e.source_ip:
                q = self._fail_times.setdefault(ip, deque())
                q.append(e.ts)
                while q and q[0] < e.ts - BRUTE_WINDOW:
                    q.popleft()
                if len(q) >= BRUTE_THRESHOLD and not self._cooling(("brute", ip), e.ts, BRUTE_COOLDOWN):
                    self._emit(out, e.ts, "crit", "bruteforce",
                               f"{ip} から5分間に{len(q)}回のログイン失敗（総当たりの可能性）", e.source_ip)

        current = {(p["proto"], p["port"]): p for p in listening if (p["proto"], p["port"]) not in self._ignore_ports}
        if self._known_ports is None:
            self._known_ports = set(current)
        else:
            for key in sorted(set(current) - self._known_ports):
                p = current[key]
                where = "外部公開" if p["exposed"] else "ローカルのみ"
                self._emit(out, now, "warn", "new_port",
                           f"新しい待ち受けポート {p['proto']}/{p['port']}（{clip(p['process'], 40)}・{where}）")
            self._known_ports |= set(current)

        for c in connections:
            label = SUSPICIOUS_REMOTE_PORTS.get(c.remote_port)
            if label is None or self._cooling(("out", c.remote_ip, c.remote_port), now, OUTBOUND_COOLDOWN):
                continue
            note = f"・{label}" if label else ""
            self._emit(out, now, "warn", "suspicious_outbound",
                       f"不審なポートへの通信 {c.remote_ip}:{c.remote_port}{note}（{clip(c.process, 40)}）",
                       c.remote_ip)
        return out

    def recent(self, n: int = 50) -> list[dict]:
        return list(reversed(self._alerts))[:n]
