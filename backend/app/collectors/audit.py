"""依存ライブラリの脆弱性チェック（pip-audit / npm audit）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .. import runner
from .history import clip

SEVERITIES = ("critical", "high", "moderate", "low", "unknown")
AUDIT_TIMEOUT = 300


@dataclass(frozen=True)
class Finding:
    source: str  # "pip" | "npm"
    project: str
    package: str
    version: str
    vuln_id: str
    severity: str
    fix: str
    title: str = ""
    aliases: list[str] = field(default_factory=list)


def _load(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def parse_pip_audit(text: str, project: str) -> list[Finding]:
    data = _load(text)
    if not data:
        return []
    out = []
    for dep in data.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        for v in dep.get("vulns") or []:
            fixes = v.get("fix_versions") or []
            out.append(
                Finding(
                    source="pip",
                    project=project,
                    package=clip(str(dep.get("name", "")), 80),
                    version=clip(str(dep.get("version", "")), 40),
                    vuln_id=clip(str(v.get("id", "")), 60),
                    severity="unknown",  # pip-audit は重大度を返さない
                    fix=clip(str(fixes[0]), 40) if fixes else "",
                    title=clip(str(v.get("description", "")), 200),
                    aliases=[clip(str(a), 40) for a in (v.get("aliases") or [])][:5],
                )
            )
    return out


def _npm_fix(fix: object) -> str:
    if fix is True:
        return "npm audit fix"
    if isinstance(fix, dict) and fix.get("name"):
        return clip(f"{fix.get('name')}@{fix.get('version', '')}", 60)
    return ""


def parse_npm_audit(text: str, project: str) -> list[Finding]:
    data = _load(text)
    if not data:
        return []
    out = []
    for name, v in (data.get("vulnerabilities") or {}).items():
        if not isinstance(v, dict):
            continue
        via = v.get("via") or []
        advisory = next((x for x in via if isinstance(x, dict)), None)
        if advisory:
            url = str(advisory.get("url", ""))
            vuln_id = url.rsplit("/", 1)[-1] if "/advisories/" in url else str(advisory.get("title", ""))
            title = str(advisory.get("title", ""))
        else:
            vuln_id = "via " + ", ".join(str(x) for x in via)
            title = ""
        sev = str(v.get("severity", "unknown"))
        out.append(
            Finding(
                source="npm",
                project=project,
                package=clip(str(v.get("name", name)), 80),
                version=clip(str(v.get("range", "")), 40),
                vuln_id=clip(vuln_id, 60),
                severity="low" if sev == "info" else (sev if sev in SEVERITIES else "unknown"),
                fix=_npm_fix(v.get("fixAvailable")),
                title=clip(title, 200),
            )
        )
    return out


class AuditRunner:
    def __init__(self, frontend_dir: Path, extra_paths: list[Path]) -> None:
        self.frontend_dir = frontend_dir
        self.extra_paths = extra_paths

    def _targets(self) -> list[tuple[str, str, str, Path | None]]:
        """(表示名, source, コマンド名, cwd)"""
        targets: list[tuple[str, str, str, Path | None]] = [("このアプリ (Python)", "pip", "pip_audit_env", None)]
        if (self.frontend_dir / "package-lock.json").is_file():
            targets.append(("このアプリ (frontend)", "npm", "npm_audit", self.frontend_dir))
        for p in self.extra_paths:
            if (p / "requirements.txt").is_file():
                targets.append((p.name or str(p), "pip", "pip_audit_requirements", p))
            if (p / "package-lock.json").is_file():
                targets.append((p.name or str(p), "npm", "npm_audit", p))
            if not p.is_dir():
                targets.append((str(p), "-", "", None))
        return targets

    def run_once(self) -> dict:
        findings: list[Finding] = []
        statuses = []
        for label, source, cmd, cwd in self._targets():
            if not cmd:
                statuses.append({"name": label, "source": source, "state": "error", "message": "ディレクトリがありません"})
                continue
            state, message = "ok", ""
            try:
                res = runner.run(cmd, cwd=cwd, timeout=AUDIT_TIMEOUT)
            except runner.CommandUnavailable:
                state, message = "unavailable", "ツールが見つかりません"
            except runner.CommandFailed as exc:
                state, message = "error", str(exc)
            else:
                data = _load(res.stdout)
                if "No module named pip_audit" in res.stderr:
                    state, message = "unavailable", "pip-audit がインストールされていません"
                elif data is None:
                    state, message = "error", "出力を解析できません"
                elif source == "npm" and isinstance(data.get("error"), dict):
                    state, message = "error", clip(str(data["error"].get("code", "npm error")), 60)
                else:
                    parse = parse_pip_audit if source == "pip" else parse_npm_audit
                    findings.extend(parse(res.stdout, project=label))
            statuses.append({"name": label, "source": source, "state": state, "message": message})

        counts = dict.fromkeys(SEVERITIES, 0)
        for f in findings:
            counts[f.severity] += 1
        return {
            "last_run": datetime.now(UTC).isoformat(),
            "targets": statuses,
            "findings": [asdict(f) for f in findings],
            "counts": counts,
        }
