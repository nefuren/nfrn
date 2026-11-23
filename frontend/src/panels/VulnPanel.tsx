import { formatTime } from "../lib/format";
import type { AuditReport, Finding } from "../lib/types";

const ORDER: Finding["severity"][] = ["critical", "high", "moderate", "low", "unknown"];
const SHORT = { critical: "CRIT", high: "HIGH", moderate: "MOD", low: "LOW", unknown: "UNK" } as const;

function stateLine(audit: AuditReport): string {
  switch (audit.state) {
    case "pending":
      return "待機中（起動の数秒後にスキャン）";
    case "running":
      return "スキャン中…";
    case "error":
      return "スキャンに失敗しました";
    default:
      return `最終スキャン ${formatTime(audit.last_run)}（6時間ごと）`;
  }
}

export function VulnPanel({ audit }: { audit: AuditReport | undefined }) {
  if (!audit) return <p className="empty">取得中…</p>;
  const findings = [...audit.findings].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  const problems = audit.targets.filter((t) => t.state !== "ok");
  return (
    <div className="stack">
      <div className="sev-row">
        {ORDER.map((s) => (
          <span key={s} className={`sev sev--${s} ${(audit.counts[s] ?? 0) > 0 ? "sev--hit" : ""}`}>
            <b className="num">{audit.counts[s] ?? 0}</b>
            <span>{SHORT[s]}</span>
          </span>
        ))}
      </div>
      <p className="foot">{stateLine(audit)}</p>
      {problems.map((t) => (
        <p key={`${t.name}-${t.source}`} className="banner banner--warn">
          {t.name}: {t.message}
        </p>
      ))}
      {audit.state === "done" && !findings.length && !problems.length && (
        <p className="empty empty--ok">既知の脆弱性はありません</p>
      )}
      <ul className="vulns">
        {findings.map((f, i) => (
          <li key={`${f.project}-${f.package}-${f.vuln_id}-${i}`} className={`vuln vuln--${f.severity}`}>
            <span className={`sev-badge sev--${f.severity}`}>{SHORT[f.severity]}</span>
            <span className="vuln__pkg">
              {f.package} <span className="num muted">{f.version}</span>
            </span>
            <span className="vuln__id num">{f.vuln_id}</span>
            <span className="vuln__fix">{f.fix ? `→ ${f.fix}` : "修正版なし"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
