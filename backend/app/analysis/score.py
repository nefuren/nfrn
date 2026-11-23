"""セキュリティスコア（100点からの減点方式。内訳つき）。"""

from __future__ import annotations

from dataclasses import dataclass, field

RISKY_PORTS = {
    21: "FTP", 23: "Telnet", 135: "RPC", 139: "NetBIOS", 445: "SMB", 1433: "MSSQL", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 9200: "Elasticsearch",
    11211: "memcached", 27017: "MongoDB",
}
VULN_POINTS = {"critical": 10, "high": 5, "moderate": 2, "low": 1, "unknown": 1}


@dataclass
class ScoreContext:
    firewall_profiles: dict[str, bool | None] = field(default_factory=dict)
    listening: list[dict] = field(default_factory=list)
    failures_1h: int = 0
    lockouts_24h: int = 0
    vuln_counts: dict[str, int] = field(default_factory=dict)
    dashboard_exposed: bool = False


def compute_score(ctx: ScoreContext) -> dict:
    items: list[dict] = []
    notes: list[str] = []

    def deduct(label: str, points: int) -> None:
        if points:
            items.append({"label": label, "points": -abs(points)})

    disabled = [name for name, on in ctx.firewall_profiles.items() if on is False]
    if disabled:
        deduct(f"ファイアウォール無効：{', '.join(disabled)}", 25)
    if ctx.firewall_profiles and all(v is None for v in ctx.firewall_profiles.values()):
        notes.append("ファイアウォールの状態を読めませんでした")
    elif not ctx.firewall_profiles:
        notes.append("ファイアウォールの状態はこのOSでは未対応です")

    exposed_tcp = sorted({p["port"] for p in ctx.listening if p["exposed"] and p["proto"] == "tcp"})
    risky = [p for p in exposed_tcp if p in RISKY_PORTS]
    other = [p for p in exposed_tcp if p not in RISKY_PORTS]
    if risky:
        names = ", ".join(f"{p}({RISKY_PORTS[p]})" for p in risky)
        deduct(f"危険なポートを公開：{names}", min(5 * len(risky), 15))
    if other:
        deduct(f"その他の公開TCPポート：{len(other)}個", min(len(other), 5))

    if ctx.failures_1h >= 10:
        deduct(f"直近1時間のログイン失敗：{ctx.failures_1h}回", 15)
    elif ctx.failures_1h >= 1:
        deduct(f"直近1時間のログイン失敗：{ctx.failures_1h}回", 5)
    if ctx.lockouts_24h:
        deduct(f"24時間以内のアカウントロック：{ctx.lockouts_24h}回", 10)

    vuln_points = sum(VULN_POINTS.get(sev, 1) * n for sev, n in ctx.vuln_counts.items())
    if vuln_points:
        total = sum(ctx.vuln_counts.values())
        deduct(f"依存ライブラリの脆弱性：{total}件", min(vuln_points, 30))

    if ctx.dashboard_exposed:
        deduct("ダッシュボードがループバック以外で待ち受け", 20)

    value = max(0, min(100, 100 + sum(i["points"] for i in items)))
    return {"value": value, "items": items, "notes": notes}
