"""Windows ファイアウォールの有効/無効をレジストリから読む（コマンド出力の言語に依存しない）。"""

from __future__ import annotations

import sys
from collections.abc import Callable

# (表示名, 論理キー)。ローカル設定ではプライベートは StandardProfile という名前
PROFILES = [("Domain", "DomainProfile"), ("Private", "PrivateProfile"), ("Public", "PublicProfile")]
_POLICY = r"SOFTWARE\Policies\Microsoft\WindowsFirewall"
_LOCAL = r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy"
_LOCAL_NAMES = {"PrivateProfile": "StandardProfile"}

Reader = Callable[[str, str], "int | None"]


def _winreg_reader(scope: str, profile: str) -> int | None:
    import winreg  # Windows のみ

    base = _POLICY if scope == "policy" else _LOCAL
    name = profile if scope == "policy" else _LOCAL_NAMES.get(profile, profile)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{base}\{name}") as key:
            value, _ = winreg.QueryValueEx(key, "EnableFirewall")
            return int(value)
    except OSError:
        return None


def firewall_state(reader: Reader | None = None, is_windows: bool | None = None) -> dict:
    if reader is None:
        windows = sys.platform == "win32" if is_windows is None else is_windows
        if not windows:
            return {"available": False, "profiles": {}}
        reader = _winreg_reader
    profiles: dict[str, bool | None] = {}
    for label, key in PROFILES:
        value = reader("policy", key)  # グループポリシーが優先
        if value is None:
            value = reader("local", key)
        profiles[label] = None if value is None else bool(value)
    return {"available": True, "profiles": profiles}
