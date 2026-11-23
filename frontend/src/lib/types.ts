// バックエンド（backend/app/monitor.py）が WebSocket で送るメッセージの型

export interface ScoreItem {
  label: string;
  points: number;
}
export interface Score {
  value: number;
  items: ScoreItem[];
  notes: string[];
}

export interface SystemSample {
  cpu: number;
  cpu_per_core: number[];
  mem: number;
  mem_used: number;
  mem_total: number;
  swap: number;
  uptime: number;
  processes: number;
}

export interface NetSample {
  rx_bps: number;
  tx_bps: number;
  rx_total: number;
  tx_total: number;
}

export interface Remote {
  ip: string;
  country: string;
  count: number;
  ports: number[];
  processes: string[];
  private: boolean;
}

export interface TickMessage {
  type: "tick";
  ts: string;
  system: SystemSample;
  net: NetSample;
  remotes: Remote[];
  connections_total: number;
  score: Score;
}

export interface ListeningPort {
  proto: "tcp" | "udp";
  address: string;
  port: number;
  pid: number | null;
  process: string;
  exposed: boolean;
}

export interface LoginEventView {
  ts: string;
  kind: "failure" | "success" | "lockout";
  user: string;
  source_ip: string | null;
  detail: string;
}

export interface SourceStatus {
  state: "ok" | "pending" | "no_permission" | "unavailable" | "error";
  message: string;
  source: string;
}

export interface Alert {
  id: number;
  ts: string;
  level: "info" | "warn" | "crit";
  kind: string;
  message: string;
  source_ip: string | null;
}

export interface Finding {
  source: "pip" | "npm";
  project: string;
  package: string;
  version: string;
  vuln_id: string;
  severity: "critical" | "high" | "moderate" | "low" | "unknown";
  fix: string;
  title: string;
  aliases: string[];
}

export interface AuditReport {
  state: "pending" | "running" | "done" | "error";
  last_run: string | null;
  targets: { name: string; source: string; state: string; message: string }[];
  findings: Finding[];
  counts: Partial<Record<Finding["severity"], number>>;
}

export interface SlowMessage {
  type: "slow";
  ts: string;
  host: { hostname: string; os: string; cores: number; geoip: boolean };
  ports: ListeningPort[];
  firewall: { available: boolean; profiles: Record<string, boolean | null> };
  logins: {
    status: SourceStatus;
    failures_per_minute: number[];
    failures_1h: number;
    failures_24h: number;
    success_24h: number;
    lockouts_24h: number;
    recent: LoginEventView[];
  };
  alerts: Alert[];
  audit: AuditReport;
  score: Score;
}

export type ConnectionStatus = "connecting" | "live" | "reconnecting";
