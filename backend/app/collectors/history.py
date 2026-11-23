"""ログイン関連イベントの型と履歴。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

Kind = Literal["failure", "success", "lockout"]

MAX_TEXT = 64


def clip(value: str | None, limit: int = MAX_TEXT) -> str:
    """外部由来の文字列を長さだけ制限する（中身の解釈・置換はしない）。"""
    if not value:
        return ""
    return value if len(value) <= limit else value[: limit - 1] + "…"


@dataclass(frozen=True)
class LoginEvent:
    ts: datetime  # タイムゾーン付き
    kind: Kind
    user: str
    source_ip: str | None
    detail: str
    key: str  # 重複除去用

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        del d["key"]
        return d


class LoginHistory:
    def __init__(self, max_events: int = 5000) -> None:
        self._max = max_events
        self._events: dict[str, LoginEvent] = {}

    def add(self, events: list[LoginEvent]) -> list[LoginEvent]:
        new = []
        for e in events:
            if e.key not in self._events:
                self._events[e.key] = e
                new.append(e)
        if len(self._events) > self._max:
            keep = sorted(self._events.values(), key=lambda e: e.ts)[-self._max :]
            self._events = {e.key: e for e in keep}
        return sorted(new, key=lambda e: e.ts)

    def recent(self, n: int = 50) -> list[LoginEvent]:
        return sorted(self._events.values(), key=lambda e: e.ts, reverse=True)[:n]

    def count(self, kind: Kind, since: datetime) -> int:
        return sum(1 for e in self._events.values() if e.kind == kind and e.ts >= since)

    def failures_per_minute(self, now: datetime, minutes: int = 60) -> list[int]:
        buckets = [0] * minutes
        for e in self._events.values():
            if e.kind != "failure":
                continue
            idx = int((now - e.ts).total_seconds() // 60)
            if 0 <= idx < minutes:
                buckets[minutes - 1 - idx] += 1
        return buckets
