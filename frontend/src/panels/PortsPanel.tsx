import type { ListeningPort, SlowMessage } from "../lib/types";

function rank(p: ListeningPort): number {
  return (p.risky && p.exposed ? 0 : p.exposed ? 1 : 2) * 100000 + p.port;
}

export function PortsPanel({ ports, firewall }: { ports: ListeningPort[]; firewall: SlowMessage["firewall"] | undefined }) {
  const sorted = [...ports].sort((a, b) => rank(a) - rank(b));
  return (
    <div className="stack">
      {firewall?.available && (
        <div className="chips" aria-label="Windows ファイアウォール">
          <span className="chips__k">FIREWALL</span>
          {Object.entries(firewall.profiles).map(([name, on]) => (
            <span key={name} className={`chip ${on === true ? "chip--on" : on === false ? "chip--off" : "chip--unk"}`}>
              <span>{name}</span> <b>{on === true ? "ON" : on === false ? "OFF" : "?"}</b>
            </span>
          ))}
        </div>
      )}
      <table className="tbl">
        <thead>
          <tr>
            <th>PORT</th>
            <th>ADDR</th>
            <th>PROCESS</th>
            <th>範囲</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => (
            <tr key={`${p.proto}-${p.address}-${p.port}`} className={p.risky && p.exposed ? "row--danger" : ""}>
              <td className="num">
                {p.port}
                <span className="proto">/{p.proto}</span>
                {p.risky && <span className="tag tag--danger">{p.risky}</span>}
              </td>
              <td className="num ellipsis">{p.address}</td>
              <td className="ellipsis">{p.process}</td>
              <td>
                <span className={`badge ${p.exposed ? "badge--exposed" : "badge--local"}`}>
                  {p.exposed ? "公開" : "ローカル"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!ports.length && <p className="empty">待ち受けポートを取得中…</p>}
    </div>
  );
}
