"""通信量・通信先・待ち受けポート。psutil（OS の API）から取得し、コマンド出力は解析しない。"""

from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import psutil

from .geoip import GeoIP
from .system import ProcessNames

MAX_REMOTES = 60


@dataclass(frozen=True)
class Connection:
    proto: str
    local_port: int
    remote_ip: str
    remote_port: int
    pid: int | None
    process: str


def raw_connections() -> list[Any]:
    try:
        return psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        return []


def _proto(conn: Any) -> str:
    return "udp" if conn.type == socket.SOCK_DGRAM else "tcp"


def _is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def parse_connections(raw: Iterable[Any], names: ProcessNames) -> list[Connection]:
    out = []
    for c in raw:
        if not c.raddr:
            continue
        proto = _proto(c)
        if proto == "tcp" and c.status != "ESTABLISHED":
            continue
        rip = c.raddr.ip
        if _is_loopback(rip):
            continue
        out.append(Connection(proto, c.laddr.port if c.laddr else 0, rip, c.raddr.port, c.pid, names.name(c.pid)))
    return out


def aggregate_remotes(conns: list[Connection], geo: GeoIP, limit: int = MAX_REMOTES) -> list[dict]:
    groups: dict[str, dict] = {}
    for c in conns:
        g = groups.setdefault(c.remote_ip, {"count": 0, "ports": set(), "processes": set()})
        g["count"] += 1
        g["ports"].add(c.remote_port)
        g["processes"].add(c.process)
    result = []
    for ip, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
        country = geo.lookup(ip)
        result.append(
            {
                "ip": ip,
                "country": country,
                "count": g["count"],
                "ports": sorted(g["ports"])[:5],
                "processes": sorted(g["processes"])[:3],
                "private": country in ("LAN", "LOCAL"),
            }
        )
    return result[:limit]


def listening_ports(raw: Iterable[Any], names: ProcessNames) -> list[dict]:
    seen: dict[tuple[str, str, int], dict] = {}
    for c in raw:
        proto = _proto(c)
        if not c.laddr:
            continue
        if proto == "tcp" and c.status != "LISTEN":
            continue
        if proto == "udp" and c.raddr:
            continue
        addr = c.laddr.ip.split("%", 1)[0]
        key = (proto, addr, c.laddr.port)
        if key in seen:
            continue
        seen[key] = {
            "proto": proto,
            "address": addr,
            "port": c.laddr.port,
            "pid": c.pid,
            "process": names.name(c.pid),
            "exposed": not _is_loopback(addr),
        }
    return sorted(seen.values(), key=lambda p: (p["port"], p["proto"], p["address"]))


class NetRate:
    def __init__(
        self,
        counters: Callable[[], Any] = psutil.net_io_counters,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._counters = counters
        self._clock = clock
        first = counters()
        self._last = (clock(), first.bytes_recv, first.bytes_sent)

    def sample(self) -> dict:
        c = self._counters()
        now = self._clock()
        t0, rx0, tx0 = self._last
        dt = max(now - t0, 1e-6)
        self._last = (now, c.bytes_recv, c.bytes_sent)
        return {
            "rx_bps": max(c.bytes_recv - rx0, 0) / dt,
            "tx_bps": max(c.bytes_sent - tx0, 0) / dt,
            "rx_total": c.bytes_recv,
            "tx_total": c.bytes_sent,
        }
