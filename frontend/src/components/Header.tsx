import { useNow } from "../hooks/useNow";
import type { ConnectionStatus } from "../lib/types";

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connecting: "CONNECTING",
  live: "LIVE",
  reconnecting: "RECONNECTING",
};

interface Props {
  hostname?: string;
  os?: string;
  status: ConnectionStatus;
  score?: number;
  onLogout: () => void;
}

export function Header({ hostname, os, status, score, onLogout }: Props) {
  const now = useNow();
  const scoreTone = score === undefined ? "" : score >= 80 ? "lime" : score >= 50 ? "orange" : "magenta";
  return (
    <header className="header">
      <div className="header__brand">
        <h1 className="logo">
          IP TEST <span className="logo__accent">DESK</span>
        </h1>
        <span className="header__tag">SECURITY MONITOR</span>
      </div>
      <div className="header__host">
        <span className="kv">
          <span className="kv__k">HOST</span>
          <span className="kv__v">{hostname ?? "—"}</span>
        </span>
        <span className="kv">
          <span className="kv__k">OS</span>
          <span className="kv__v">{os ?? "—"}</span>
        </span>
        <span className="kv">
          <span className="kv__k">SCORE</span>
          <span className={`kv__v num tone-${scoreTone}`}>{score ?? "—"}</span>
        </span>
      </div>
      <div className="header__right">
        <span className={`status status--${status}`} aria-live="polite">
          <span className="status__dot" />
          {STATUS_LABEL[status]}
        </span>
        <time className="clock num" dateTime={now.toISOString()}>
          {now.toLocaleTimeString("ja-JP", { hour12: false })}
        </time>
        <button className="btn btn--ghost" type="button" onClick={onLogout}>
          LOGOUT
        </button>
      </div>
    </header>
  );
}
