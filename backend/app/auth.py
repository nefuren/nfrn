"""トークン認証とセッション管理。

ブラウザはトークンを一度だけ POST し、以後はランダムなセッションIDを HttpOnly Cookie で持つ。
トークン自体を Cookie や URL に載せないことで、ログや履歴への漏えいを防ぐ。
"""

from __future__ import annotations

import hmac
import secrets
import time
from collections import OrderedDict, deque
from collections.abc import Callable

COOKIE_NAME = "desk_session"
MAX_SESSIONS = 32


def token_matches(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


class SessionStore:
    def __init__(self, ttl_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._sessions: OrderedDict[str, float] = OrderedDict()

    def create(self) -> str:
        self._purge()
        while len(self._sessions) >= MAX_SESSIONS:
            self._sessions.popitem(last=False)
        sid = secrets.token_urlsafe(32)
        self._sessions[sid] = self._clock() + self._ttl
        return sid

    def valid(self, sid: str | None) -> bool:
        if not sid:
            return False
        expiry = self._sessions.get(sid)
        if expiry is None:
            return False
        if expiry <= self._clock():
            self._sessions.pop(sid, None)
            return False
        return True

    def revoke(self, sid: str | None) -> None:
        if sid:
            self._sessions.pop(sid, None)

    def _purge(self) -> None:
        now = self._clock()
        for sid in [s for s, exp in self._sessions.items() if exp <= now]:
            del self._sessions[sid]


class RateLimiter:
    """一定時間内の失敗回数で制限する。"""

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        q = self._failures.setdefault(key, deque())
        cutoff = self._clock() - self._window
        while q and q[0] <= cutoff:
            q.popleft()
        return q

    def allow(self, key: str) -> bool:
        return len(self._recent(key)) < self._max

    def record_failure(self, key: str) -> None:
        self._recent(key).append(self._clock())
