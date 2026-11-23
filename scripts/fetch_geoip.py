"""DB-IP Lite（国別・無料・CC BY 4.0）の mmdb を backend/data/ に取得する。

使い方（リポジトリ直下で）:  python scripts/fetch_geoip.py
国判定はこのローカルファイルだけで行い、通信先 IP を外部へ送ることはありません。
"""

from __future__ import annotations

import gzip
import sys
import urllib.request
from datetime import date
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "backend" / "data" / "dbip-country-lite.mmdb"
URL = "https://download.db-ip.com/free/dbip-country-lite-{ym}.mmdb.gz"
MAX_BYTES = 64 * 1024 * 1024
MMDB_MARKER = b"\xab\xcd\xefMaxMind.com"


def _months() -> list[str]:
    today = date.today()
    prev = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)
    return [f"{today:%Y-%m}", f"{prev:%Y-%m}"]


def main() -> int:
    for ym in _months():
        url = URL.format(ym=ym)
        print(f"取得中: {url}")
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310  固定の https URL のみ
                data = resp.read(MAX_BYTES + 1)
        except OSError as exc:
            print(f"  失敗: {exc}")
            continue
        if len(data) > MAX_BYTES:
            print("  サイズが大きすぎます")
            return 1
        try:
            raw = gzip.decompress(data)
        except OSError:
            print("  gzip として展開できません")
            continue
        if MMDB_MARKER not in raw[-200_000:]:
            print("  mmdb 形式ではありません")
            continue
        DEST.parent.mkdir(parents=True, exist_ok=True)
        tmp = DEST.with_suffix(".tmp")
        tmp.write_bytes(raw)
        tmp.replace(DEST)
        print(f"保存しました: {DEST}  ({len(raw) // 1024} KiB)")
        print("出典表示: IP Geolocation by DB-IP (https://db-ip.com) — CC BY 4.0")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
