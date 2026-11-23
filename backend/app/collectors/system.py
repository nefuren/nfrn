"""CPU・メモリなどのシステム情報とプロセス名の解決。"""

from __future__ import annotations

import platform
import socket
import time

import psutil


class ProcessNames:
    """PID → プロセス名（キャッシュ付き）。権限がなければ "?"。"""

    def __init__(self, ttl_seconds: float = 60) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[int, str] = {}
        self._stamp = time.monotonic()

    def name(self, pid: int | None) -> str:
        if not pid:
            return "System" if pid == 0 else "?"
        if time.monotonic() - self._stamp > self._ttl:
            self._cache.clear()
            self._stamp = time.monotonic()
        if pid not in self._cache:
            try:
                self._cache[pid] = psutil.Process(pid).name()[:64]
            except (psutil.Error, OSError):
                self._cache[pid] = "?"
        return self._cache[pid]


class SystemCollector:
    def __init__(self) -> None:
        psutil.cpu_percent(interval=None)  # 初回は 0 が返るので呼んでおく
        psutil.cpu_percent(interval=None, percpu=True)
        self.hostname = socket.gethostname()[:64]
        self.os = f"{platform.system()} {platform.release()}"[:64]
        self.boot_time = psutil.boot_time()

    def sample(self) -> dict:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "cpu_per_core": psutil.cpu_percent(interval=None, percpu=True),
            "mem": vm.percent,
            "mem_used": vm.used,
            "mem_total": vm.total,
            "swap": sw.percent,
            "uptime": int(time.time() - self.boot_time),
            "processes": len(psutil.pids()),
        }

    def info(self) -> dict:
        return {"hostname": self.hostname, "os": self.os, "cores": psutil.cpu_count() or 0}
