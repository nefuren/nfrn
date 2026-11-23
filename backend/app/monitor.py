"""収集ループ。1秒ごとの tick と 10秒ごとの slow を作り、最新のスナップショットを保持する。"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from .analysis.alerts import AlertEngine
from .analysis.score import RISKY_PORTS, ScoreContext, compute_score
from .collectors.audit import AuditRunner
from .collectors.firewall import firewall_state
from .collectors.geoip import GeoIP
from .collectors.history import LoginHistory
from .collectors.logins_linux import LinuxLoginSource
from .collectors.logins_windows import WindowsLoginSource
from .collectors.network import NetRate, aggregate_remotes, listening_ports, parse_connections, raw_connections
from .collectors.system import ProcessNames, SystemCollector
from .config import REPO_DIR, Settings

log = logging.getLogger("desk.monitor")

FAST_INTERVAL = 1.0
SLOW_INTERVAL = 10.0
AUDIT_FIRST_DELAY = 5.0


def _now() -> datetime:
    return datetime.now(UTC)


class Monitor:
    def __init__(self, settings: Settings, *, login_source: Any = None, audit_runner: Any = None,
                 is_windows: bool | None = None) -> None:
        self.settings = settings
        windows = sys.platform == "win32" if is_windows is None else is_windows
        self.system = SystemCollector()
        self.rate = NetRate()
        self.names = ProcessNames()
        self.geo = GeoIP.from_path(settings.geoip_db)
        self.logins = login_source or (WindowsLoginSource() if windows else LinuxLoginSource(settings.auth_log))
        self.audit = audit_runner or AuditRunner(REPO_DIR / "frontend", settings.audit_paths)
        self.history = LoginHistory()
        self.alerts = AlertEngine(ignore_ports=frozenset({("tcp", settings.port)}))

        self._raw: list[Any] = []
        self._conns: list = []
        self._login_status: dict = {"state": "pending", "message": "", "source": ""}
        self._firewall: dict = {"available": False, "profiles": {}}
        self._ports: list[dict] = []
        self._audit: dict = {"state": "pending", "last_run": None, "targets": [], "findings": [],
                             "counts": {}}
        self._score: dict = {"value": 100, "items": [], "notes": []}
        self._tick: dict = {}
        self._slow: dict = {}
        self._tasks: list[asyncio.Task] = []

    # ---------- 公開 API ----------

    async def start(self) -> None:
        await self._fast_step()
        await self._slow_step()
        self._tasks = [
            asyncio.create_task(self._loop(self._fast_step, FAST_INTERVAL), name="desk-fast"),
            asyncio.create_task(self._loop(self._slow_step, SLOW_INTERVAL), name="desk-slow"),
            asyncio.create_task(self._audit_loop(), name="desk-audit"),
        ]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    def tick(self) -> dict:
        return {**self._tick, "score": self._score} if self._tick else {}

    def slow(self) -> dict:
        return self._slow

    def snapshot(self) -> dict:
        return {"tick": self.tick(), "slow": self._slow}

    # ---------- ループ ----------

    async def _loop(self, step, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await step()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001  1回の失敗で配信を止めない
                log.exception("collector step failed")

    async def _audit_loop(self) -> None:
        await asyncio.sleep(AUDIT_FIRST_DELAY)
        while True:
            self._audit = {**self._audit, "state": "running"}
            try:
                report = await asyncio.to_thread(self.audit.run_once)
                self._audit = {**report, "state": "done"}
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("audit failed")
                self._audit = {**self._audit, "state": "error"}
            await asyncio.sleep(self.settings.audit_interval_seconds)

    async def _fast_step(self) -> None:
        raw = await asyncio.to_thread(raw_connections)
        conns = parse_connections(raw, self.names)
        self._raw, self._conns = raw, conns
        self._tick = {
            "type": "tick",
            "ts": _now().isoformat(),
            "system": self.system.sample(),
            "net": self.rate.sample(),
            "remotes": aggregate_remotes(conns, self.geo),
            "connections_total": len(conns),
        }

    async def _slow_step(self) -> None:
        now = _now()
        events, status = await asyncio.to_thread(self.logins.fetch)
        new_events = self.history.add(events)
        self._login_status = status
        self._ports = [
            {**p, "risky": RISKY_PORTS.get(p["port"]) if p["proto"] == "tcp" else None}
            for p in listening_ports(self._raw, self.names)
        ]
        self._firewall = await asyncio.to_thread(firewall_state)
        self.alerts.evaluate(now, new_events, self._ports, self._conns)

        failures_1h = self.history.count("failure", now - timedelta(hours=1))
        lockouts_24h = self.history.count("lockout", now - timedelta(hours=24))
        self._score = compute_score(
            ScoreContext(
                firewall_profiles=self._firewall["profiles"],
                listening=self._ports,
                failures_1h=failures_1h,
                lockouts_24h=lockouts_24h,
                vuln_counts=self._audit.get("counts") or {},
                dashboard_exposed=not self.settings.is_loopback(),
            )
        )
        self._slow = {
            "type": "slow",
            "ts": now.isoformat(),
            "host": {**self.system.info(), "geoip": self.geo.available},
            "ports": self._ports,
            "firewall": self._firewall,
            "logins": {
                "status": self._login_status,
                "failures_per_minute": self.history.failures_per_minute(now, 60),
                "failures_1h": failures_1h,
                "failures_24h": self.history.count("failure", now - timedelta(hours=24)),
                "success_24h": self.history.count("success", now - timedelta(hours=24)),
                "lockouts_24h": lockouts_24h,
                "recent": [e.to_dict() for e in self.history.recent(20)],
            },
            "alerts": self.alerts.recent(50),
            "audit": self._audit,
            "score": self._score,
        }
