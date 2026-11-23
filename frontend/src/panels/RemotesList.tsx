import type { Remote } from "../lib/types";

export function RemotesList({ remotes, limit = 12 }: { remotes: Remote[]; limit?: number }) {
  if (!remotes.length) return <p className="empty">外部との接続はありません</p>;
  return (
    <table className="tbl tbl--remotes">
      <thead>
        <tr>
          <th>国</th>
          <th>IP</th>
          <th className="r">接続</th>
          <th>プロセス</th>
        </tr>
      </thead>
      <tbody>
        {remotes.slice(0, limit).map((r) => (
          <tr key={r.ip}>
            <td>
              <span className={`cc ${r.private ? "cc--lan" : ""}`}>{r.country}</span>
            </td>
            <td className="num">{r.ip}</td>
            <td className="num r">{r.count}</td>
            <td className="ellipsis">{r.processes.join(", ")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
