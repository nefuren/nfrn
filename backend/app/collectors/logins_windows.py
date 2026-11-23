"""Windows のセキュリティイベントログ（4624 / 4625 / 4740）を読む。

実行ユーザーを「Event Log Readers」グループに入れれば管理者権限は不要。
"""

from __future__ import annotations

from datetime import UTC, datetime

from defusedxml import ElementTree as SafeET

from .. import runner
from .history import LoginEvent, clip

NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

LOGON_TYPES = {
    "2": "対話型",
    "3": "ネットワーク",
    "4": "バッチ",
    "5": "サービス",
    "7": "ロック解除",
    "8": "ネットワーク(平文)",
    "9": "別資格情報",
    "10": "リモートデスクトップ",
    "11": "キャッシュ",
}
# 成功ログオンのうち人の操作に近いものだけを残す
INTERESTING_SUCCESS_TYPES = {"2", "7", "10", "11"}
NOISE_USERS = {"SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE", "ANONYMOUS LOGON"}


def _parse_ts(value: str) -> datetime | None:
    # 例: 2026-11-23T09:12:03.1234567Z（小数部が7桁のことがある）
    if not value:
        return None
    v = value.rstrip("Z")
    if "." in v:
        head, frac = v.split(".", 1)
        v = f"{head}.{frac[:6]}"
    try:
        return datetime.fromisoformat(v).replace(tzinfo=UTC)
    except ValueError:
        return None


def _is_noise_user(user: str) -> bool:
    return (
        not user
        or user == "-"
        or user.endswith("$")
        or user.upper() in NOISE_USERS
        or user.startswith(("DWM-", "UMFD-"))
    )


def parse_windows_events(xml_text: str) -> list[LoginEvent]:
    text = xml_text.strip()
    if not text:
        return []
    try:
        # wevtutil は <Event> を並べて出力するのでルートで包む。DTD/実体参照は defusedxml が拒否する。
        root = SafeET.fromstring(f"<Events>{text}</Events>")
    except Exception:  # noqa: BLE001  壊れた出力・XXE などはすべて「データなし」扱い
        return []

    events: list[LoginEvent] = []
    for ev in root.findall("e:Event", NS):
        event_id = ev.findtext("e:System/e:EventID", default="", namespaces=NS).strip()
        record_id = ev.findtext("e:System/e:EventRecordID", default="", namespaces=NS).strip()
        tc = ev.find("e:System/e:TimeCreated", NS)
        ts = _parse_ts(tc.get("SystemTime", "") if tc is not None else "")
        if ts is None or not record_id:
            continue
        data = {
            d.get("Name", ""): (d.text or "").strip()
            for d in ev.findall("e:EventData/e:Data", NS)
        }
        user = data.get("TargetUserName", "")
        ip = data.get("IpAddress", "")
        source_ip = None if ip in ("", "-") else ip
        logon_type = data.get("LogonType", "")
        type_label = LOGON_TYPES.get(logon_type, f"種別{clip(logon_type, 8)}")

        if event_id == "4625":
            kind, detail = "failure", f"{type_label}ログオン失敗"
        elif event_id == "4740":
            kind, detail = "lockout", "アカウントロック"
        elif event_id == "4624":
            if logon_type not in INTERESTING_SUCCESS_TYPES or _is_noise_user(user):
                continue
            kind, detail = "success", f"{type_label}ログオン"
        else:
            continue

        events.append(
            LoginEvent(
                ts=ts,
                kind=kind,
                user=clip(user),
                source_ip=clip(source_ip, 45) if source_ip else None,
                detail=detail,
                key=f"win:{record_id}",
            )
        )
    return events


def _status(state: str, message: str = "") -> dict:
    return {"state": state, "message": message, "source": "Windows セキュリティログ"}


class WindowsLoginSource:
    def fetch(self) -> tuple[list[LoginEvent], dict]:
        events: list[LoginEvent] = []
        for name in ("wevtutil_failures", "wevtutil_success"):
            try:
                res = runner.run(name, timeout=20)
            except runner.CommandUnavailable:
                return [], _status("unavailable", "wevtutil が見つかりません")
            except runner.CommandFailed as exc:
                return events, _status("error", str(exc))
            if res.returncode == 5 or "denied" in res.stderr.lower() or "拒否" in res.stderr:
                return [], _status(
                    "no_permission",
                    "セキュリティログを読む権限がありません（Event Log Readers グループへの追加が必要）",
                )
            if res.returncode != 0:
                # 該当イベントが 0 件のときも非 0 を返す場合がある
                if res.stdout.strip() == "" and not res.stderr.strip():
                    continue
                return events, _status("error", clip(res.stderr.strip().splitlines()[0] if res.stderr.strip()
                                                     else f"終了コード {res.returncode}", 120))
            events.extend(parse_windows_events(res.stdout))
        return events, _status("ok")
