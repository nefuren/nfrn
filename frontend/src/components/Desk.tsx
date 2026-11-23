import { useEffect, useMemo, useState } from "react";
import { useDeskSocket } from "../hooks/useDeskSocket";
import { appendSample, type Sample } from "../lib/series";
import { AlertsPanel } from "../panels/AlertsPanel";
import { LoginPanel } from "../panels/LoginPanel";
import { PortsPanel } from "../panels/PortsPanel";
import { RemotesList } from "../panels/RemotesList";
import { ScorePanel } from "../panels/ScorePanel";
import { SystemPanel } from "../panels/SystemPanel";
import { TrafficPanel } from "../panels/TrafficPanel";
import { VulnPanel } from "../panels/VulnPanel";
import { NetworkMap } from "../viz/NetworkMap";
import { Header } from "./Header";
import { Panel } from "./Panel";

interface Props {
  onUnauthorized: () => void;
  onLogout: () => void;
}

export function Desk({ onUnauthorized, onLogout }: Props) {
  const { status, tick, slow } = useDeskSocket({ onUnauthorized });
  const [series, setSeries] = useState<Sample[]>([]);
  useEffect(() => {
    if (tick) setSeries((s) => appendSample(s, tick));
  }, [tick]);

  const score = tick?.score ?? slow?.score;
  const ports = slow?.ports ?? [];
  const exposed = ports.filter((p) => p.exposed).length;
  const alerts = useMemo(() => slow?.alerts ?? [], [slow]);
  const crit = alerts.filter((a) => a.level === "crit").length;
  const alertIps = useMemo(
    () => [...new Set(alerts.map((a) => a.source_ip).filter((ip): ip is string => !!ip))],
    [alerts],
  );
  const remotes = useMemo(() => tick?.remotes ?? [], [tick]);
  const vulnTotal = slow ? Object.values(slow.audit.counts).reduce((a, b) => a + (b ?? 0), 0) : 0;

  return (
    <div className="desk">
      <Header hostname={slow?.host.hostname} os={slow?.host.os} status={status} score={score?.value} onLogout={onLogout} />
      <main className="grid">
        <div className="col col--left">
          <Panel title="SECURITY SCORE" code="L-01" accent="lime">
            <ScorePanel score={score} />
          </Panel>
          <Panel title="LOGIN FAILURES" code="L-02" accent="magenta">
            <LoginPanel logins={slow?.logins} />
          </Panel>
          <Panel title="SYSTEM LOAD" code="L-03" accent="cyan">
            <SystemPanel tick={tick} series={series} />
          </Panel>
        </div>

        <div className="col col--center">
          <Panel title="TRAFFIC" code="C-01" accent="cyan">
            <TrafficPanel tick={tick} series={series} />
          </Panel>
          <Panel
            title="NETWORK MAP"
            code="C-02"
            accent="magenta"
            className="panel--map"
            aside={<span className="aside num">{tick?.remotes.length ?? 0} NODES</span>}
          >
            <div className="map">
              <NetworkMap remotes={remotes} alertIps={alertIps} hostname={slow?.host.hostname} />
              <div className="map__list">
                <RemotesList remotes={remotes} limit={30} />
              </div>
            </div>
          </Panel>
        </div>

        <div className="col col--right">
          <Panel
            title="OPEN PORTS"
            code="R-01"
            accent="orange"
            aside={<span className="aside num">{ports.length} / 公開 {exposed}</span>}
          >
            <PortsPanel ports={ports} firewall={slow?.firewall} />
          </Panel>
          <Panel
            title="ALERTS"
            code="R-02"
            accent="magenta"
            aside={crit > 0 ? <span className="aside aside--crit num">CRIT {crit}</span> : undefined}
          >
            <AlertsPanel alerts={alerts} />
          </Panel>
          <Panel
            title="VULNERABILITIES"
            code="R-03"
            accent="lime"
            aside={<span className="aside num">{vulnTotal} 件</span>}
          >
            <VulnPanel audit={slow?.audit} />
          </Panel>
        </div>
      </main>
    </div>
  );
}
