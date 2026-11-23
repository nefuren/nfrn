"""IP → 国コード。ローカルの mmdb だけを使い、IP を外部へ送らない。"""

from __future__ import annotations

import ipaddress
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("desk.geoip")

UNKNOWN = "??"
CACHE_LIMIT = 4096


class GeoIP:
    def __init__(self, reader: Any | None) -> None:
        self._reader = reader
        self._cache: dict[str, str] = {}

    @classmethod
    def from_path(cls, path: Path | None) -> GeoIP:
        if path is None or not path.is_file():
            if path is not None:
                log.warning("GeoIP DB が見つかりません: %s（国は ?? と表示）", path)
            return cls(reader=None)
        import maxminddb

        try:
            return cls(reader=maxminddb.open_database(str(path)))
        except (OSError, ValueError) as exc:
            log.warning("GeoIP DB を開けません: %s", exc.__class__.__name__)
            return cls(reader=None)

    @property
    def available(self) -> bool:
        return self._reader is not None

    def lookup(self, ip: str) -> str:
        cached = self._cache.get(ip)
        if cached is not None:
            return cached
        try:
            addr = ipaddress.ip_address(ip.split("%", 1)[0])
        except ValueError:
            return UNKNOWN
        if addr.is_loopback:
            result = "LOCAL"
        elif addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
            result = "LAN"
        else:
            result = self._lookup_public(str(addr))
        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[ip] = result
        return result

    def _lookup_public(self, ip: str) -> str:
        if self._reader is None:
            return UNKNOWN
        try:
            rec = self._reader.get(ip)
        except ValueError:
            return UNKNOWN
        if not isinstance(rec, dict):
            return UNKNOWN
        code = (rec.get("country") or {}).get("iso_code")
        return code if isinstance(code, str) and len(code) == 2 else UNKNOWN
