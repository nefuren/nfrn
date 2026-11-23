import { useDeskSocket } from "../hooks/useDeskSocket";
import { formatBytesPerSec, formatPct } from "../lib/format";
import { Header } from "./Header";
import { Panel, Placeholder } from "./Panel";

interface Props {
  onUnauthorized: () => void;
  onLogout: () => void;
}

export function Desk({ onUnauthorized, onLogout }: Props) {
  const { status, tick, slow } = useDeskSocket({ onUnauthorized });
  const score = tick?.score ?? slow?.score;
  const vulnTotal = slow ? Object.values(slow.audit.counts).reduce((a, b) => a + (b ?? 0), 0) : undefined;

  return (
    <div className="desk">
      <Header
        hostname={slow?.host.hostname}
        os={slow?.host.os}
        status={status}
        score={score?.value}
        onLogout={onLogout}
      />
      <main className="grid">
        <div className="col col--left">
          <Panel title="SECURITY SCORE" code="L-01" accent="lime">
            <Placeholder value={score?.value ?? "—"} label="/ 100" note={`減点 ${score?.items.length ?? 0} 件`} />
          </Panel>
          <Panel title="LOGIN FAILURES" code="L-02" accent="magenta">
            <Placeholder value={slow?.logins.failures_1h ?? "—"} label="直近1時間" note={slow?.logins.status.source} />
          </Panel>
          <Panel title="SYSTEM LOAD" code="L-03" accent="cyan">
            <Placeholder
              value={formatPct(tick?.system.cpu)}
              label="CPU"
              note={`MEM ${formatPct(tick?.system.mem)}`}
            />
          </Panel>
        </div>

        <div className="col col--center">
          <Panel title="TRAFFIC" code="C-01" accent="cyan">
            <Placeholder
              value={tick ? formatBytesPerSec(tick.net.rx_bps) : "—"}
              label="受信"
              note={`送信 ${tick ? formatBytesPerSec(tick.net.tx_bps) : "—"}`}
            />
          </Panel>
          <Panel title="NETWORK MAP" code="C-02" accent="magenta" className="panel--map">
            <Placeholder value={tick?.remotes.length ?? "—"} label="通信先" note="段階4でアニメーション表示" />
          </Panel>
        </div>

        <div className="col col--right">
          <Panel title="OPEN PORTS" code="R-01" accent="orange">
            <Placeholder
              value={slow?.ports.length ?? "—"}
              label="待ち受け"
              note={`外部公開 ${slow?.ports.filter((p) => p.exposed).length ?? "—"}`}
            />
          </Panel>
          <Panel title="ALERTS" code="R-02" accent="magenta">
            <Placeholder value={slow?.alerts.length ?? "—"} label="履歴" />
          </Panel>
          <Panel title="VULNERABILITIES" code="R-03" accent="lime">
            <Placeholder value={vulnTotal ?? "—"} label="件" note={slow?.audit.state} />
          </Panel>
        </div>
      </main>
    </div>
  );
}
