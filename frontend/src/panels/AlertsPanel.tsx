import { useEffect, useRef } from "react";
import { formatTime } from "../lib/format";
import type { Alert } from "../lib/types";

const LEVEL = { crit: "CRIT", warn: "WARN", info: "INFO" } as const;

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  // 前回表示した最大 id より新しいものを点滅させる
  const seen = useRef<number | null>(null);
  const maxId = alerts.reduce((m, a) => Math.max(m, a.id), 0);
  const threshold = seen.current;
  useEffect(() => {
    seen.current = maxId;
  }, [maxId]);

  if (!alerts.length) return <p className="empty empty--ok">異常なし — 検知ルールに該当するイベントはありません</p>;
  return (
    <ul className="alerts">
      {alerts.map((a) => (
        <li
          key={a.id}
          className={`alert alert--${a.level} ${threshold !== null && a.id > threshold ? "alert--new" : ""}`}
        >
          <span className="alert__level">{LEVEL[a.level] ?? "INFO"}</span>
          <span className="alert__time num">{formatTime(a.ts)}</span>
          <span className="alert__msg">{a.message}</span>
        </li>
      ))}
    </ul>
  );
}
